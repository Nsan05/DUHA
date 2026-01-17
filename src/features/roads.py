import geopandas as gpd
import osmnx as ox
import pandas as pd
from pathlib import Path
import logging
import sys
import numpy as np
import rasterio
from rasterio.features import rasterize
from rasterio.transform import from_origin
from rasterio.windows import Window
from shapely.geometry import box

# Configure Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Config
BASE_DIR = Path(__file__).parent.parent.parent
MASK_FILE = BASE_DIR / "data" / "raw" / "boundaries" / "urban_dubai_communities.geojson"
GRID_META_FILE = BASE_DIR / "data" / "intermediate" / "grids" / "reference_grid_meta.json"
RASTER_MASK_FILE = BASE_DIR / "data" / "intermediate" / "masks" / "urban_mask_30m.tif"
OUTPUT_RASTER = BASE_DIR / "data" / "intermediate" / "urban_form" / "road_density_30m.tif"

# Target CRS
TARGET_CRS = "EPSG:32640"

def load_urban_polygon():
    logger.info(f"Loading Urban Mask from {MASK_FILE}...")
    if not MASK_FILE.exists():
        logger.error("Mask file not found!")
        sys.exit(1)
        
    gdf = gpd.read_file(MASK_FILE)
    # Ensure it's in WGS84 for OSMnx querying
    if gdf.crs.to_epsg() != 4326:
        gdf = gdf.to_crs("EPSG:4326")
        
    # Dissolve to single geometry
    urban_poly = gdf.unary_union
    logger.info("Mask loaded and dissolved.")
    return urban_poly

def fetch_and_filter_roads(urban_poly):
    logger.info("Downloading OSM Road Network (Drive)... This may take 1-2 minutes.")
    
    # 1. Download Graph
    # simplify=True cleans up the graph topology
    # Note: simple download returns WGS84
    G = ox.graph_from_polygon(urban_poly, network_type='drive', simplify=True)
    logger.info(f"Graph downloaded (WGS84). Nodes: {len(G.nodes)}, Edges: {len(G.edges)}")
    
    # 1b. Project Graph IMMEDIATELY
    # This avoids all the headaches of reprojecting 100k lines later
    logger.info(f"Projecting graph to {TARGET_CRS}...")
    G_proj = ox.project_graph(G, to_crs=TARGET_CRS)
    
    # 2. Convert to GeoFrames
    # edges=True gets the line segments
    gdf_nodes, gdf_edges = ox.graph_to_gdfs(G_proj)
    
    # 3. Filter Columns (Keep only what we need)
    # 'highway' is the class, 'lanes' is the width info
    cols_to_keep = ['highway', 'lanes', 'length', 'geometry', 'name']
    # Filter only columns that exist (avoid errors if 'name' is missing)
    cols_to_keep = [c for c in cols_to_keep if c in gdf_edges.columns]
    gdf_edges = gdf_edges[cols_to_keep]
    
    # 4. Standardize 'highway' column
    # Sometimes 'highway' is a list (e.g. ['tertiary', 'residential']). Take first.
    gdf_edges['highway'] = gdf_edges['highway'].apply(lambda x: x[0] if isinstance(x, list) else x)
    
    return gdf_edges

def analyze_stats(gdf):
    logger.info("-" * 40)
    logger.info("ANALYSIS: RAW DATA STATISTICS")
    logger.info("-" * 40)
    
    total = len(gdf)
    logger.info(f"Total Road Segments: {total:,}")
    
    # Check Lanes
    # 'lanes' column might be object (string/list) or float.
    # Convert to numeric, errors='coerce' to turn bad data to NaN
    # But first handle lists if any
    
    def parse_lanes(val):
        if isinstance(val, list):
            val = val[0] # Take first element if list
            
        if pd.isna(val) or val in [None, 'None', '']: 
            return None
            
        try:
            return float(val)
        except:
            return None
            
    gdf['lanes_clean'] = gdf['lanes'].apply(parse_lanes)
    
    with_lanes = gdf['lanes_clean'].notna().sum()
    missing_lanes = total - with_lanes
    
    logger.info(f"Segments with Lane Data: {with_lanes:,} ({with_lanes/total*100:.1f}%)")
    logger.info(f"Segments MISSING Lane Data: {missing_lanes:,} ({missing_lanes/total*100:.1f}%)")
    
    logger.info("-" * 40)
    logger.info("MISSING LANES BY HIGHWAY CLASS:")
    logger.info(f"{'Class':<20} | {'Total':<8} | {'Missing':<8} | {'% Missing'}")
    logger.info("-" * 40)
    
    # Group by highway
    stats = gdf.groupby('highway')['lanes_clean'].apply(lambda x: x.isna().sum()).reset_index(name='missing_count')
    counts = gdf['highway'].value_counts().reset_index(name='total_count')
    # rename column for merge
    counts.rename(columns={'index': 'highway', 'highway': 'highway'}, inplace=True) # pandas version handling
    # Just merge
    # Recent pandas uses 'highway' for both
    
    merged = pd.merge(stats, counts, on='highway')
    merged['pct_missing'] = (merged['missing_count'] / merged['total_count']) * 100
    
    # Sort by importance (total count)
    merged = merged.sort_values('total_count', ascending=False)
    
    for _, row in merged.iterrows():
        logger.info(f"{row['highway']:<20} | {row['total_count']:<8} | {row['missing_count']:<8} | {row['pct_missing']:.1f}%")
        
    return gdf


def impute_widths(gdf):
    logger.info("-" * 40)
    logger.info("IMPUTATION & WIDTH CALCULATION")
    logger.info("-" * 40)
    
    # 1. Calc Medians
    medians = gdf.groupby('highway')['lanes_clean'].median()
    
    # Fill NaN medians with a global fallback (e.g. 2 lanes / 7m)
    # If a class is completely missing (like 'tertiary_link' maybe), it needs a default.
    GLOBAL_DEFAULT = 2.0
    medians = medians.fillna(GLOBAL_DEFAULT)
    
    logger.info("LEARNED MEDIANS (Lanes):")
    for cls, val in medians.items():
        logger.info(f"  {cls:<20}: {val:.1f}")
        
    # 2. Impute
    # Create 'lanes_final'
    def fill_lanes(row):
        if pd.notna(row['lanes_clean']):
            return row['lanes_clean']
        else:
            hw = row['highway']
            if hw in medians:
                return medians[hw]
            return GLOBAL_DEFAULT
            
    gdf['lanes_final'] = gdf.apply(fill_lanes, axis=1)
    
    # 3. Calculate Width
    # Standard: 3.5m per lane
    LANE_WIDTH_M = 3.5
    gdf['width_m'] = gdf['lanes_final'] * LANE_WIDTH_M
    
    # 4. Caps
    MIN_WIDTH = 6.0   # Min 6m (approx 2 lanes narrow)
    MAX_WIDTH = 60.0  # Max 60m (Sheikh Zayed Road max)
    
    # Apply Caps
    gdf['width_m'] = gdf['width_m'].clip(lower=MIN_WIDTH, upper=MAX_WIDTH)
    
    # Stats
    logger.info("-" * 40)
    logger.info("WIDTH STATISTICS:")
    logger.info(f"Min Width: {gdf['width_m'].min()}m")
    logger.info(f"Max Width: {gdf['width_m'].max()}m")
    logger.info(f"Mean Width: {gdf['width_m'].mean():.2f}m")
    
    return gdf


def create_road_polygons(gdf, urban_poly):
    logger.info("-" * 40)
    logger.info("BUFFER & CLIP GEOMETRY")
    logger.info("-" * 40)
    # 1. Reproject (Already done in Step 1, but good to check)
    logger.info(f"Geometry CRS: {gdf.crs}")

    urban_poly_proj = gpd.GeoSeries([urban_poly], crs="EPSG:4326").to_crs(TARGET_CRS)[0]
    
    # 2. Buffer
    logger.info("Buffering lines to polygons...")
    
    # buffer() returns a GeoSeries - This extends out the line to both ways
    buffered_series = gdf.apply(lambda row: row.geometry.buffer(row['width_m'] / 2, cap_style=1), axis=1)

    # Set geometry
    gdf['geometry'] = buffered_series
    gdf.set_geometry('geometry', inplace=True, crs=TARGET_CRS)
    
    # 3. Dissolve
    logger.info("Dissolving overlapping roads...")
    union_geom = gdf.unary_union
    
    if union_geom.is_empty:
        logger.error("CRITICAL: unary_union returned EMPTY geometry!")
        return None

    road_surface = gpd.GeoSeries([union_geom], crs=TARGET_CRS)
    
    # 4. Clip to Urban Mask
    logger.info("Clipping to Urban Boundaries...")
    
    # Check intersection - incase if the buffer pushed any roads out of the border
    final_surface = road_surface.intersection(urban_poly_proj)
    
    # Calculate Area Stats
    total_area_km2 = final_surface.area.sum() / 1e6
    logger.info(f"Total Paved Road Surface: {total_area_km2:.2f} km²")
    
    return final_surface

def rasterize_roads(road_surface, urban_poly):
    logger.info("-" * 40)
    logger.info("RASTERIZATION (Super-Sampling)")
    logger.info("-" * 40)
    
    # Ensure Output Directory Exists
    OUTPUT_RASTER.parent.mkdir(parents=True, exist_ok=True)
    
    # Open the Mask to get Grid Definition
    with rasterio.open(RASTER_MASK_FILE) as src:
        profile = src.profile.copy()
        transform = src.transform
        width = src.width
        height = src.height
        
        # Update Profile for Float Density
        profile.update(
            dtype=rasterio.float32,
            count=1,
            nodata=np.nan,
            compress='lzw'
        )
        
        # Prepare Output
        logger.info(f"Creating {OUTPUT_RASTER} ({width}x{height})...")
        
        # Super-Sampling Factor
        FACTOR = 10 
        
        with rasterio.open(OUTPUT_RASTER, 'w', **profile) as dst:
            
            # Create windows (blocks) to process
            # 2048 seems like a good chunk size
            block_size = 1024
            windows = []
            for j in range(0, height, block_size):
                for i in range(0, width, block_size):
                    # Calculate window size handling edges
                    w = min(block_size, width - i)
                    h = min(block_size, height - j)
                    windows.append(Window(i, j, w, h))
            
            total_windows = len(windows)
            logger.info(f"Processing {total_windows} windows with {FACTOR}x super-sampling...")
            
            for idx, win in enumerate(windows):
                if idx % 10 == 0:
                    logger.info(f" Window {idx+1}/{total_windows}...")
                
                # 1. Define Window Bounds
                win_transform = src.window_transform(win)
                win_bounds = rasterio.windows.bounds(win, transform)
                # Box for filtering (buffer slightly to catch edge cases)
                win_box = box(*win_bounds)
                
                # 2. Check overlap
                # road_surface is a GeoSeries. intersects returns a Series of bools.
                # if the road surface doesnt intersect w the window box, then we will just store 0s masked to urban dubai 
                if not road_surface.intersects(win_box).any():
                    # No roads here -> Write NaNs or 0s regarding mask

                    mask_data = src.read(1, window=win)
                    out_arr = np.full(mask_data.shape, 0.0, dtype=np.float32)
                    out_arr[mask_data == 0] = np.nan
                    dst.write(out_arr, window=win, indexes=1)
                    continue
                
                # 3. Super-Sampling
                # Create High-Res Grid for this window
                super_w = win.width * FACTOR
                super_h = win.height * FACTOR
                
                # Super Transform
                super_transform = win_transform * win_transform.scale(1/FACTOR, 1/FACTOR)
                
                # Rasterize Geometry onto Super Grid
                # We need a single geometry or list of geometries for rasterize()
                # road_surface is a GeoSeries. intersection() returns a GeoSeries.
                local_series = road_surface.intersection(win_box)
                
                # Filter out pure empty parts
                local_series = local_series[~local_series.is_empty]
                
                if local_series.empty:
                    mask_data = src.read(1, window=win)
                    out_arr = np.full(mask_data.shape, 0.0, dtype=np.float32)
                    out_arr[mask_data == 0] = np.nan
                    dst.write(out_arr, window=win, indexes=1)
                    continue
                
                # Prepare shapes for rasterize: list of (geometry, value)
                shapes = [(geom, 1) for geom in local_series]
                
                # Rasterize (Binary: 1=Road, 0=Empty)
                super_arr = rasterize(
                    shapes,
                    out_shape=(super_h, super_w),
                    transform=super_transform,
                    fill=0,
                    dtype=np.uint8,
                    all_touched=False # Standard center-point for super-pixels is fine
                )
                
                # 4. Downsample (Mean)
                # Reshape to (H, Factor, W, Factor) and take mean
                reshaped = super_arr.reshape(win.height, FACTOR, win.width, FACTOR)
                density = reshaped.mean(axis=(1, 3)).astype(np.float32)
                
                # 5. Apply Urban Mask
                mask_data = src.read(1, window=win)
                density[mask_data == 0] = np.nan
                
                # 6. Write
                dst.write(density, window=win, indexes=1)
                
    logger.info("Done! Road Density Raster saved.")

if __name__ == "__main__":
    poly = load_urban_polygon()
    roads = fetch_and_filter_roads(poly)
    roads = analyze_stats(roads)
    roads = impute_widths(roads)
    road_surface = create_road_polygons(roads, poly)
    if road_surface is not None:
        rasterize_roads(road_surface, poly)


