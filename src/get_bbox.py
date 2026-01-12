import json
import rasterio
from rasterio.warp import transform_bounds
from pathlib import Path

META_FILE = Path("data/intermediate/grids/reference_grid_meta.json")

def get_bbox():
    with open(META_FILE, 'r') as f:
        meta = json.load(f)
        
    # Get bounds in EPSG:32640
    # Transform: [res_x, 0, origin_x, 0, res_y, origin_y]
    # But rasterio stores it as [a, b, c, d, e, f]
    # affine.Affine(a, b, c, d, e, f)
    # meta['transform'] list is [30.0, 0.0, 201585.0, 0.0, -30.0, 2833815.0]
    
    tf = meta['transform']
    width = meta['width']
    height = meta['height']
    crs = meta['crs']
    
    left = tf[2]
    top = tf[5]
    right = left + (width * tf[0])
    bottom = top + (height * tf[4]) # tf[4] is negative (-30)
    
    print(f"Projected Bounds (EPSG:32640): {left}, {bottom}, {right}, {top}")
    
    # Convert to WGS84 (EPSG:4326)
    wgs_left, wgs_bottom, wgs_right, wgs_top = transform_bounds(crs, "EPSG:4326", left, bottom, right, top)
    
    print(f"WGS84 BBox: {wgs_left},{wgs_bottom},{wgs_right},{wgs_top}")

if __name__ == "__main__":
    get_bbox()
