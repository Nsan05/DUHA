import json
from pathlib import Path
import geopandas as gpd
import rasterio
from rasterio.features import rasterize
import numpy as np

BASE_DIR = Path(__file__).parent.parent
MASK_INPUT_FILE = BASE_DIR / "data" / "raw" / "boundaries" / "urban_dubai_communities.geojson"
GRID_META_FILE = BASE_DIR / "data" / "intermediate" / "grids" / "reference_grid_meta.json"
OUTPUT_DIR = BASE_DIR / "data" / "intermediate" / "masks"
OUTPUT_FILE = OUTPUT_DIR / "urban_mask_30m.tif"

def create_urban_mask():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # 1. Load Reference Grid Metadata
    print(f"[INFO] Loading Grid Metadata from: {GRID_META_FILE}")
    with open(GRID_META_FILE, 'r') as f:
        meta = json.load(f)
    
    # Reconstruct the Transform and CRS
    project_crs = meta['crs']
    width = meta['width']
    height = meta['height']
    transform = rasterio.Affine(*meta['transform']) # Convert list back to Affine object

    print(f"       Target CRS: {project_crs}")
    print(f"       Grid Size: {width} x {height}")

    # 2. Load and Reproject Vector Data
    print(f"\n[INFO] Loading Vector Mask: {MASK_INPUT_FILE}")
    gdf = gpd.read_file(MASK_INPUT_FILE)
    
    if gdf.crs != project_crs:
        print(f"       Reprojecting from {gdf.crs} to {project_crs}...")
        gdf = gdf.to_crs(project_crs)
    else:
        print(f"       CRS already matches {project_crs}.")

    # 3. Dissolve into Single Polygon
    # This prevents boundary overlaps and simplifies rasterization
    print("       Dissolving polygons into single urban shape...")
    # 'dissolve' returns a GeoDataFrame with one row (the union of all geoms)
    # We assign a constant column to dissolve on
    gdf['dissolve_id'] = 1
    dissolved_gdf = gdf.dissolve(by='dissolve_id')
    
    # 4. Rasterize onto Master Grid
    print("\n[INFO] Rasterizing...")
    
    # rasterize() expects a list of (geometry, value) tuples
    # We use '1' for inside urban area
    shapes = ((geom, 1) for geom in dissolved_gdf.geometry)
    
    mask_array = rasterize(
        shapes=shapes,
        out_shape=(height, width),
        transform=transform,
        fill=0,       # 0 for outside
        dtype='uint8'
    )
    
    unique, counts = np.unique(mask_array, return_counts=True)
    count_dict = dict(zip(unique, counts))
    print(f"       Rasterization Complete. Pixel Counts: {count_dict}")
    print(f"       (1 = Urban: {count_dict.get(1, 0)}, 0 = Background: {count_dict.get(0, 0)})")

    # 5. Save to Disk
    profile = {
        'driver': 'GTiff',
        'dtype': 'uint8',
        'nodata': 0,
        'width': width,
        'height': height,
        'count': 1,
        'crs': project_crs,
        'transform': transform,
        'compress': 'lzw' # Good for categorical masks
    }
    
    with rasterio.open(OUTPUT_FILE, 'w', **profile) as dst:
        dst.write(mask_array, 1)
        print(f"\n[INFO] Saved Urban Mask: {OUTPUT_FILE}")

if __name__ == "__main__":
    import os
    create_urban_mask()
