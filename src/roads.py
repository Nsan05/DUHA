import geopandas as gpd
import osmnx as ox
import pandas as pd
from pathlib import Path
import logging
import sys

# Configure Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Config
BASE_DIR = Path(__file__).parent.parent
MASK_FILE = BASE_DIR / "data" / "raw" / "boundaries" / "urban_dubai_communities.geojson"
GRID_META_FILE = BASE_DIR / "data" / "intermediate" / "grids" / "reference_grid_meta.json"

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
    G = ox.graph_from_polygon(urban_poly, network_type='drive', simplify=True)
    logger.info(f"Graph downloaded. Nodes: {len(G.nodes)}, Edges: {len(G.edges)}")
    
    # 2. Convert to GeoFrames
    # edges=True gets the line segments
    gdf_nodes, gdf_edges = ox.graph_to_gdfs(G)
    
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
    logger.info("PART 1 ANALYSIS: RAW DATA STATISTICS")
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

if __name__ == "__main__":
    poly = load_urban_polygon()
    roads = fetch_and_filter_roads(poly)
    roads = analyze_stats(roads)
    # Not saving yet, just Part 1 confirmation
