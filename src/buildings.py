import json
import rasterio
from rasterio.features import rasterize
from rasterio.windows import Window
from rasterio.transform import from_origin
import numpy as np
from shapely.geometry import shape, box
from shapely.ops import transform
from shapely.prepared import prep
import pyproj
from shapely.strtree import STRtree
import geopandas as gpd
from pathlib import Path
import logging
import os

# ==========================================
# CONFIGURATION
# ==========================================
BASE_DIR = Path(__file__).parent.parent
INPUT_FILE = BASE_DIR / "data" / "raw" / "overture" / "buildings.geojsonseq"
OUTPUT_DIR = BASE_DIR / "data" / "intermediate" / "urban_form"
OUTPUT_FILE = OUTPUT_DIR / "building_density_30m.tif"
GRID_META_FILE = BASE_DIR / "data" / "intermediate" / "grids" / "reference_grid_meta.json"
URBAN_BOUNDARIES_FILE = BASE_DIR / "data" / "raw" / "boundaries" / "urban_dubai_communities.geojson"

# Super-sampling factor (10x = 3m resolution for 30m target)
SCALE_FACTOR = 10 

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def load_master_meta():
    with open(GRID_META_FILE, 'r') as f:
        return json.load(f)

def load_urban_polygon(target_crs):
    """
    Loads the urban boundaries, reprojects, and dissolves into a single geometry.
    """
    logger.info("Loading Urban Mask Polygon...")
    if not URBAN_BOUNDARIES_FILE.exists():
        logger.error(f"Urban file not found: {URBAN_BOUNDARIES_FILE}")
        return None
        
    # Read file
    gdf = gpd.read_file(URBAN_BOUNDARIES_FILE)
    
    # Reproject
    if gdf.crs.to_string() != target_crs:
        # Normalize CRS string just in case
        # target_crs is likely "EPSG:32640"
        gdf = gdf.to_crs(target_crs)
        
    # Dissolve to single "Urban" geometry
    # unary_union is efficient and we dont use dissolve becasu that outputs a gdf which is suitable for rasterization but this returns a geometry object which is suitable for 'intersects' spatial filtering
    urban_poly = gdf.unary_union
    logger.info("Urban Mask Polygon loaded and dissolved.")
    return urban_poly

def load_and_reproject_buildings(target_crs):
    """
    Reads GeoJSONSeq, reprojects to target_crs, FILTERS by Urban Mask, and returns geometries.
    """
    # 1. Prepare Urban Mask
    # using the polygon from before
    urban_poly = load_urban_polygon(target_crs)
    urban_prep = None
    if urban_poly is None:
        logger.warning("Proceeding WITHOUT Urban Mask filtering (File missing).")
    else:
        logger.info("Preparing Urban Mask for spatial filtering...")
        urban_prep = prep(urban_poly)

    logger.info("Loading and reprojecting buildings... This may take a moment.")
    
    # Input is WGS84 (EPSG:4326)
    wgs84 = pyproj.CRS("EPSG:4326")
    target = pyproj.CRS(target_crs)
    # building transformer object that will be used later in loop with transform()
    project = pyproj.Transformer.from_crs(wgs84, target, always_xy=True).transform # (long, lat)
    
    buildings = []
    skipped_count = 0
    
    if not INPUT_FILE.exists():
         logger.error(f"Input file not found: {INPUT_FILE}")
         return []

    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        for i, line in enumerate(f):
            # skip empty lines
            if not line.strip(): continue
            try:
                feat = json.loads(line)
                geom = shape(feat['geometry'])
                
                # Reproject
                reprojected_geom = transform(project, geom)
                
                # FILTER: Check if inside Urban Mask
                if urban_prep is not None:
                    # Quick check: does it intersect?
                    if not urban_prep.intersects(reprojected_geom):
                        skipped_count += 1
                        continue 

                buildings.append(reprojected_geom)
                
            except Exception as e:
                logger.warning(f"Skipping feature {i}: {e}")
                
    logger.info(f"Loaded {len(buildings)} buildings.")
    if skipped_count > 0:
        logger.info(f"Filtered out {skipped_count} buildings outside the urban mask.")
        
    return buildings

def process_block(window_30m, tree, all_buildings, meta, scale=SCALE_FACTOR):
    """
    Rasterizes buildings for a given window using super-sampling. (get acc coordinates, look for buildings, convert to 3m grid, downsample to 30m)
    """
    # 1. Define bounds of the 30m window
    mt = meta['transform']
    # Window origin (Top-Left)
    x_min = mt[2] + (window_30m.col_off * mt[0])
    y_max = mt[5] + (window_30m.row_off * mt[4]) 
    
    # Window width/height in projected units - because we are only processing for a block here 
    w_proj = window_30m.width * mt[0]
    h_proj = window_30m.height * abs(mt[4])
    
    x_max = x_min + w_proj
    y_min = y_max - h_proj
    
    # 2. Query Index - finding buildings in this window
    window_box = box(x_min, y_min, x_max, y_max)
    indices = tree.query(window_box)
    
    # If no buildings found, return an empty black square
    if len(indices) == 0:
        return np.zeros((window_30m.height, window_30m.width), dtype='float32')

    window_buildings = [all_buildings[i] for i in indices]
    
    # 3. Create Super-Resolution Grid (3m)
    super_w = window_30m.width * scale
    super_h = window_30m.height * scale
    
    # New transform for the 3m grid
    # Pixel size is mt[0]/scale (3m)
    # y_res is negative in affine, so we use abs() / scale - shear anf tilt elements set to 0 when using from_origin()
    # from_origin(West, North, Pixel_Width, Pixel_Height) - convienient method for creating an affine transform
    super_transform = from_origin(x_min, y_max, mt[0]/scale, abs(mt[4])/scale)

    # 4. Rasterize onto Super-Grid (Binary)
    shapes = [(g, 1) for g in window_buildings]
    
    # takes the coordinatees and burns it into the new grid
    super_mask = rasterize(
        shapes=shapes,
        out_shape=(super_h, super_w),
        transform=super_transform,
        fill=0,
        dtype='uint8'
    )
    
    # 5. Downsample (Average) to 30m
    reshaped = super_mask.reshape(window_30m.height, scale, window_30m.width, scale)
    density = reshaped.mean(axis=(1, 3)).astype('float32')
    
    return density

# Get all the buildings in urban reprojected and make a tree
# read the urban mask
# make output file
# make the blocks
# iterate thru each block, how many buildings in each block
# accordingly make a 3m grid with that info - rasterisation
# downsample fom 3m to 30m mean density
# from output make all the non urban -1
# save the file
def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    meta = load_master_meta()
    
    # Load and Index
    buildings = load_and_reproject_buildings(meta['crs'])
    if not buildings:
        logger.error("No buildings loaded. Exiting.")
        return

    logger.info("Building Spatial Index...")
    tree = STRtree(buildings)
    logger.info("Index built.")
    
    # Path to Raster Mask
    RASTER_MASK_FILE = BASE_DIR / "data" / "intermediate" / "masks" / "urban_mask_30m.tif"
    if not RASTER_MASK_FILE.exists():
        logger.error(f"Raster mask not found: {RASTER_MASK_FILE}")
        return

    # Prepare Output
    out_profile = {
        'driver': 'GTiff',
        'width': meta['width'],
        'height': meta['height'],
        'crs': meta['crs'],
        'transform': rasterio.Affine(*meta['transform']),
        'count': 1,
        'dtype': 'float32',
        'nodata': np.nan,  # Standard NaN for float data
        'compress': 'lzw',
        'tiled': True
    }
    
    BLOCK_SIZE = 1024 
    W, H = meta['width'], meta['height']
    
    with rasterio.open(OUTPUT_FILE, 'w', **out_profile) as dst:
        with rasterio.open(RASTER_MASK_FILE) as mask_src:
            total_blocks = ((W + BLOCK_SIZE - 1) // BLOCK_SIZE) * ((H + BLOCK_SIZE - 1) // BLOCK_SIZE)
            processed = 0
            
            for col_off in range(0, W, BLOCK_SIZE):
                for row_off in range(0, H, BLOCK_SIZE):
                    width = min(BLOCK_SIZE, W - col_off)
                    height = min(BLOCK_SIZE, H - row_off)
                    
                    win = Window(col_off, row_off, width, height)
                    
                    # 1. Calc Density
                    density_arr = process_block(win, tree, buildings, meta)
                    
                    # 2. Read Mask for this window
                    # Resampling shouldn't be needed if grids align
                    urban_mask = mask_src.read(1, window=win)
                    
                    # 3. Apply Mask (Set outside pixels to NODATA)
                    # urban_mask is 1 (Urban) / 0 (Outside)
                    density_arr[urban_mask == 0] = np.nan
                    
                    dst.write(density_arr, window=win, indexes=1)
                    
                    processed += 1
                    if processed % 10 == 0:
                        logger.info(f"Processed {processed}/{total_blocks} blocks...")
                    
    logger.info(f"Done. Saved to {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
