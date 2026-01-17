import os
import glob
import re
import json
from pathlib import Path
import numpy as np
import rasterio
from rasterio.warp import reproject, Resampling, transform_bounds
from rasterio.windows import Window
from rasterio.coords import BoundingBox
import logging

BASE_DIR = Path(__file__).parent.parent.parent
RAW_SENTINEL_DIR = BASE_DIR / "data" / "raw" / "sentinel2" / "scenes"
GRID_META_FILE = BASE_DIR / "data" / "intermediate" / "grids" / "reference_grid_meta.json"
URBAN_MASK_FILE = BASE_DIR / "data" / "intermediate" / "masks" / "urban_mask_30m.tif"
OUTPUT_DIR = BASE_DIR / "data" / "intermediate" / "sentinel2_30m"

# Processing Block Size (Dimensions in 10m pixels)
BLOCK_SIZE = 2052 # 684 * 3

# SCL Classes to KEEP
VALID_SCL = [2, 4, 5, 6, 7] 

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def load_master_grid_meta():
    with open(GRID_META_FILE, 'r') as f:
        meta = json.load(f)
    return meta

def find_granules():
    return list(RAW_SENTINEL_DIR.rglob("GRANULE/L2A_*"))

def find_band_path(granule_dir, band_name, res="10m"):
    search_path = granule_dir / "IMG_DATA" / f"R{res}"
    candidates = list(search_path.glob(f"*_{band_name}_{res}.jp2"))
    if not candidates:
        candidates = list(search_path.glob(f"*_{band_name}.jp2"))
    return candidates[0] if candidates else None

# Gets the bounding boxes coordinates for each granule for performance optimisation
def get_granule_bounds_projected(granule_dir, target_crs):
    ref_path = find_band_path(granule_dir, "B02", "10m")
    if not ref_path:
        return None
    with rasterio.open(ref_path) as src:
        if src.crs == target_crs:
            return src.bounds
        else:
            left, bottom, right, top = transform_bounds(src.crs, target_crs, *src.bounds)
            return BoundingBox(left, bottom, right, top)

# To get the real world coordinates of the 10m grid
def get_window_bounds(window_10m, master_meta):
    mt = master_meta['transform']
    # Calculate the Affine of the 10m grid with master grid as different datasets use different origins
    tf_10m = rasterio.Affine(mt[0]/3, mt[1], mt[2], mt[3], mt[4]/3, mt[5])
    # Top left
    x1, y1 = tf_10m * (window_10m.col_off, window_10m.row_off)
    # Bottom right
    x2, y2 = tf_10m * (window_10m.col_off + window_10m.width, window_10m.row_off + window_10m.height)
    # left, bottom, right, top
    return BoundingBox(min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2))

def format_approx_time(seconds):
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    return f"{int(h)}h {int(m)}m {int(s)}s"

def get_windowed_reprojection(src_path, master_meta, window_10m):
    mt = master_meta['transform']
    # global transform affine
    tf_10m_global = rasterio.Affine(mt[0]/3, mt[1], mt[2], mt[3], mt[4]/3, mt[5])
    # local transform affine - proper location affine of the window
    window_tf = tf_10m_global * rasterio.Affine.translation(window_10m.col_off, window_10m.row_off)
    
    # when we reproject (align them), the 10m grid form ours should match the 10m of our master grid perfectly
    # 1 is hardcoded to always choose the first layer of the passed src (which will always jsut be one)
    # The original data may be skewed and not matching the coordinates and refercnce system of the target file. We reporject so that it does match
    # It almost never fully aligns so we do resmapling to fix that 
    with rasterio.open(src_path) as src:
        dst_arr = np.zeros((window_10m.height, window_10m.width), dtype='float32')
        reproject(
            source=rasterio.band(src, 1),
            destination=dst_arr,
            src_transform=src.transform,
            src_crs=src.crs,
            dst_transform=window_tf,
            dst_crs=master_meta['crs'],
            resampling=Resampling.bilinear,
            dst_nodata=np.nan
        )
    return dst_arr

def get_windowed_scl(src_path, master_meta, window_10m):
    mt = master_meta['transform']
    tf_10m_global = rasterio.Affine(mt[0]/3, mt[1], mt[2], mt[3], mt[4]/3, mt[5])
    window_tf = tf_10m_global * rasterio.Affine.translation(window_10m.col_off, window_10m.row_off)
    

    with rasterio.open(src_path) as src:
        dst_arr = np.zeros((window_10m.height, window_10m.width), dtype='uint8')
        reproject(
            source=rasterio.band(src, 1),
            destination=dst_arr,
            src_transform=src.transform,
            src_crs=src.crs,
            dst_transform=window_tf,
            dst_crs=master_meta['crs'],
            resampling=Resampling.nearest
        )
    return dst_arr

def bounds_intersect(b1, b2):
    return not (b1.right < b2.left or b1.left > b2.right or \
                b1.top < b2.bottom or b1.bottom > b2.top)

def process_block(window_10m, relevant_granules, master_meta):
    # dict to store the values for each band, because there would be values frok multiple scenes and we pick after colelcting all
    stack = {b: [] for b in ['B02', 'B03', 'B04', 'B08', 'B11', 'B12']}
    
    for g in relevant_granules:
        scl_path = find_band_path(g, "SCL", "20m")
        if not scl_path: continue
        # get the SCL values for the window thats properlly reprojected onto the main grid
        scl_arr = get_windowed_scl(scl_path, master_meta, window_10m)
        valid_mask = np.isin(scl_arr, VALID_SCL)
        
        for b in ['B02', 'B03', 'B04', 'B08']:
            p = find_band_path(g, b, "10m")
            if p:
                arr = get_windowed_reprojection(p, master_meta, window_10m)
                arr[~valid_mask] = np.nan
                stack[b].append(arr)
                
        for b in ['B11', 'B12']:
            p = find_band_path(g, b, "20m")
            if p:
                arr = get_windowed_reprojection(p, master_meta, window_10m)
                arr[~valid_mask] = np.nan
                stack[b].append(arr)
                
    medians = {}
    for b, arrays in stack.items():
        if not arrays:
            medians[b] = np.full((window_10m.height, window_10m.width), np.nan, dtype='float32')
        else:
            big_stack = np.stack(arrays, axis=0)
            with np.errstate(invalid='ignore'):
                 medians[b] = np.nanmedian(big_stack, axis=0)
            
    b2 = medians['B02'] / 10000.0
    b3 = medians['B03'] / 10000.0
    b4 = medians['B04'] / 10000.0
    b8 = medians['B08'] / 10000.0
    b11 = medians['B11'] / 10000.0
    b12 = medians['B12'] / 10000.0
    
    with np.errstate(divide='ignore', invalid='ignore'):
        ndvi = (b8 - b4) / (b8 + b4 + 1e-6)
        ndwi = (b3 - b8) / (b3 + b8 + 1e-6)
        # BSI = ((SWIR1 + Red) - (NIR + Blue)) / ((SWIR1 + Red) + (NIR + Blue))
        bsi = ((b11 + b4) - (b8 + b2)) / ((b11 + b4) + (b8 + b2) + 1e-6)
        # MNDWI = (Green - SWIR1) / (Green + SWIR1)
        mndwi = (b3 - b11) / (b3 + b11 + 1e-6)
        albedo = (0.2266*b2) + (0.1236*b3) + (0.1573*b4) + (0.3417*b8) + (0.1170*b11) + (0.0338*b12)
    
    results = {'ndvi': ndvi, 'albedo': albedo, 'ndwi': ndwi, 'bsi': bsi, 'mndwi': mndwi}
    outputs_30m = {}
    
    for k, arr in results.items():
        h, w = arr.shape
        # this is done so that if the length is not divisble by 3 then it is made in that way and the last few pixels get ignored
        new_h = h // 3
        new_w = w // 3
        arr = arr[:new_h*3, :new_w*3]
        # the new_h index would basically contain a 3 element array
        # (big row index, tiny row index, big column index, tiny column index)
        reshaped = arr.reshape(new_h, 3, new_w, 3)
        with np.errstate(invalid='ignore'):
             mean_30m = np.nanmean(reshaped, axis=(1, 3))
        outputs_30m[k] = mean_30m
        
    return outputs_30m

def main_process():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    meta = load_master_grid_meta()
    
    all_granules = find_granules()
    logger.info(f"Found {len(all_granules)} granules. Computing bounds...")
    
    granule_bounds = {}
    target_crs = meta['crs']
    
    for g in all_granules:
        b = get_granule_bounds_projected(g, target_crs)
        if b:
            granule_bounds[g] = b
            
    logger.info("Bounds computed.")
    
    # Open Urban Mask for skipping logic
    logger.info(f"Opening Urban Mask: {URBAN_MASK_FILE}")
    urban_mask = rasterio.open(URBAN_MASK_FILE) # Keep open for windowed reading
    
    out_profile = {
        'driver': 'GTiff', 'width': meta['width'], 'height': meta['height'],
        'crs': meta['crs'], 'transform': rasterio.Affine(*meta['transform']),
        'count': 1, 'dtype': 'float32', 'nodata': -9999, 'compress': 'lzw', 'tiled': True
    }
    
    files = {}
    for name in ['ndvi', 'albedo', 'ndwi', 'bsi', 'mndwi']:
        f = rasterio.open(OUTPUT_DIR / f"{name}_30m.tif", 'w', **out_profile)
        files[name] = f
        
    W_30, H_30 = meta['width'], meta['height']
    # processing in 10m resolution
    W_10, H_10 = W_30 * 3, H_30 * 3
    BLK = 2052
    
    import time
    start_time = time.time()
    
    # total blocks with round up in case of decimals
    total_blocks = ((W_10 + BLK - 1) // BLK) * ((H_10 + BLK - 1) // BLK)
    processed_count = 0
    skipped_count = 0
    
    for col_off in range(0, W_10, BLK):
        for row_off in range(0, H_10, BLK):
            # force window to shrink towards the edges so that nothing goes out of bounds
            width = min(BLK, W_10 - col_off)
            height = min(BLK, H_10 - row_off)
            
            # Window object contians positioning info within it as well
            win_10m = Window(col_off, row_off, width, height)
            
            # --- Check Urban Mask ---
            # Mask is 30m. Window is 10m.
            # Convert 10m window to 30m window
            # col_off is 10m pixels. col_off // 3 is 30m pixels.
            win_30m = Window(col_off // 3, row_off // 3, width // 3, height // 3)
            
            # Read only the Mask Window
            try:
                mask_data = urban_mask.read(1, window=win_30m) # 1 correpsonds to the first layer, which is only 1 layer in this case. Index starts from 1 
            except Exception as e:
                # Edge case or rounding error? just proceed
                mask_data = np.ones((win_30m.height, win_30m.width)) # Force process

            # Skip if no urban pixels
            if np.all(mask_data == 0):
                # All background. Skip this heavy block.
                # logger.info(f"Block {col_off},{row_off}: Skipped (Non-Urban).")
                skipped_count += 1
                processed_count += 1
                continue
            
            # Filter Granules - find bounds of the window and check if it intersects with any granule bounds
            win_bounds = get_window_bounds(win_10m, meta)
            relevant = [g for g, buf in granule_bounds.items() if bounds_intersect(win_bounds, buf)]
            
            logger.info(f"Block {col_off},{row_off}: {len(relevant)} granules. (Urban)")
            
            if not relevant:
                processed_count += 1
                continue
                
            results_30m = process_block(win_10m, relevant, meta)
            
            for name, arr in results_30m.items():
                arr[np.isnan(arr)] = -9999
                files[name].write(arr, window=win_30m, indexes=1)
                
            processed_count += 1
            if processed_count % 5 == 0:
                elapsed = time.time() - start_time
                if processed_count > 0:
                    rate = elapsed / processed_count
                    remaining = (total_blocks - processed_count) * rate
                    logger.info(f"Progress: {processed_count}/{total_blocks} (Skipped: {skipped_count}) (Est. rem: {format_approx_time(remaining)})")
                
    for f in files.values():
        f.close()
    urban_mask.close()
    logger.info("Complete.")

if __name__ == "__main__":
    main_process()
