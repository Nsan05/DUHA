import geopandas as gpd
import osmnx as ox
from pathlib import Path
import logging

# Configure Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

BASE_DIR = Path("C:/Users/nithi/Desktop/Uni_Stuff/Y3/FYP")
MASK_FILE = BASE_DIR / "data/raw/boundaries/urban_dubai_communities.geojson"

def count_osm_buildings():
    logger.info(f"Loading Urban Mask from {MASK_FILE}...")
    
    if not MASK_FILE.exists():
        logger.error("Mask file not found!")
        return

    # 1. Load Urban Mask
    # This is a MultiPolygon of all communities
    gdf_mask = gpd.read_file(MASK_FILE)
    
    # Dissolve to get one single boundary for the query
    # (Checking against individual polygons is safer API-wise but slower in loop,
    #  checking against one giant multipolygon might timeout Overpass API).
    # Let's try the single union first.
    urban_poly = gdf_mask.unary_union
    logger.info("Mask loaded and dissolved.")

    # 2. Query OSM
    logger.info("Querying OSM for buildings (tags={'building': True})... This depends on Overpass API speed.")
    
    try:
        # geometries_from_polygon is the standard way
        # Note: Large queries might timeout. 
        # If it fails, we might need to loop through the original 'gdf_mask' rows.
        buildings = ox.features_from_polygon(urban_poly, tags={'building': True})
        
        count = len(buildings)
        logger.info("-" * 40)
        logger.info(f"OSM BUILDINGS COUNT: {count:,}")
        logger.info("-" * 40)
        
    except Exception as e:
        logger.error(f"OSM Query Failed: {e}")
        logger.info("The query might be too large for a single call. Trying iterative approach (per community)...")
        
        total_buildings = 0
        for idx, row in gdf_mask.iterrows():
            try:
                b = ox.features_from_polygon(row.geometry, tags={'building': True})
                total_buildings += len(b)
                if idx % 10 == 0:
                    logger.info(f"Scanned {idx+1}/{len(gdf_mask)} communities... Total so far: {total_buildings:,}")
            except Exception as inner_e:
                logger.warning(f"Failed for community {idx}: {inner_e}")
                
        logger.info("-" * 40)
        logger.info(f"OSM BUILDINGS COUNT (Iterative): {total_buildings:,}")
        logger.info("-" * 40)

if __name__ == "__main__":
    count_osm_buildings()
