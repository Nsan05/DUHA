import os
import glob
from pathlib import Path
import rasterio
from rasterio.warp import calculate_default_transform, reproject, Resampling
import numpy as np
import json

# Target CRS for the project
PROJECT_CRS = "EPSG:32640" 

# Directories
BASE_DIR = Path(__file__).parent.parent.parent
RAW_LANDSAT_DIR = BASE_DIR / "data" / "raw" / "landsat" / "lst"
OUTPUT_DIR = BASE_DIR / "data" / "intermediate" / "grids"
OUTPUT_FILE = OUTPUT_DIR / "master_grid_30m.tif"
META_FILE = OUTPUT_DIR / "reference_grid_meta.json"

def find_landsat_reference():
    # Recursive search for *ST_B10.TIF in the Landsat directory - used because it is consistently present and is 30m
    files = list(RAW_LANDSAT_DIR.rglob("*ST_B10.TIF"))
    if not files:
        raise FileNotFoundError(f"No *ST_B10.TIF file found in {RAW_LANDSAT_DIR}")
    
    files.sort()
    selected_file = files[0]
    print(f"[INFO] Using Reference Scene: {selected_file.name}")
    print(f"[INFO] Full Path: {selected_file}")
    return selected_file

def create_master_grid():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # Locate Reference File
    ref_path = find_landsat_reference()
    
    with rasterio.open(ref_path) as src:
        print(f"[INFO] Source CRS: {src.crs}")
        print(f"[INFO] Source Shape: {src.shape}")
        
        # Compute Transform for Target CRS (EPSG:32640)
        # If source is already in target CRS, this just passes through.
        # If not, it calculates the new bounds/transform used for reprojection.
        transform, width, height = calculate_default_transform(
            src.crs, 
            PROJECT_CRS, 
            src.width, 
            src.height, 
            *src.bounds
        )
        
        # Defining the Profile (Metadata) for the New Grid
        kwargs = src.meta.copy()
        kwargs.update({
            'crs': PROJECT_CRS,
            'transform': transform,
            'width': width,
            'height': height,
            'count': 1,            # 1 band
            'dtype': 'uint8',      # Smallest data type (binary mask / empty)
            'nodata': 0            # 0 will be the default value
        })
        
        print("\n[INFO] Master Grid Settings:")
        print(f"   CRS: {PROJECT_CRS}")
        print(f"   Resolution: {transform[0]}m, {transform[4]}m")
        print(f"   Dimensions: {width} x {height}")
        print(f"   Origin: {transform[2]}, {transform[5]}")

        # Metadata JSON (for future reference)
        # Transform is a 6-element tuple: (a, b, c, d, e, f)
        # (pixel_width, row_rotation, x_origin, column_rotation, pixel_height, y_origin)
        meta_dict = {
            "crs": PROJECT_CRS,
            "transform": [transform[0], transform[1], transform[2], 
                          transform[3], transform[4], transform[5]],
            "width": width,
            "height": height,
            "bounds": {
                "left": transform[2],
                "top": transform[5],
                "right": transform[2] + (transform[0] * width),
                "bottom": transform[5] + (transform[4] * height)
            },
            "reference_file": str(ref_path.name)
        }
        with open(META_FILE, 'w') as f:
            json.dump(meta_dict, f, indent=4)
        print(f"[INFO] Saved metadata to {META_FILE}")

        # Master Grid Raster (Empty)
        with rasterio.open(OUTPUT_FILE, 'w', **kwargs) as dst:
            empty_array = np.zeros((height, width), dtype='uint8')
            dst.write(empty_array, 1)
            print(f"[INFO] Created Master Grid: {OUTPUT_FILE}")

if __name__ == "__main__":
    create_master_grid()
