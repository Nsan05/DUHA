
import pandas as pd
import rasterio
from rasterio.windows import from_bounds
from rasterio.transform import rowcol
from pathlib import Path
import numpy as np
from tqdm import tqdm
import math

# Paths
DATA_DIR = Path("data")
RAW_GBA_DIR = DATA_DIR / "raw/GBA/OutputFiles"
CSV_PATH = DATA_DIR / "final/phase2_training_table.csv"
OUTPUT_CSV_PATH = DATA_DIR / "final/phase2_training_table_enriched.csv"

# Constants
VIIRS_RES = 750  # meters
HALF_RES = VIIRS_RES / 2

def process_gba_ultra_fast():
    if not OUTPUT_CSV_PATH.parent.exists():
        OUTPUT_CSV_PATH.parent.mkdir(parents=True)
        
    print(f"Loading CSV: {CSV_PATH}")
    df = pd.read_csv(CSV_PATH)
    
    # Initialize result columns
    # We will accumulate sum, sum of squares, and count because a 750m pixel might span 2 height tiles (tifs)
    df['gba_height_sum'] = 0.0
    df['gba_height_sum_sq'] = 0.0 # Used to compute std dev and variance
    df['gba_pixel_count'] = 0
    
    tif_files = list(RAW_GBA_DIR.glob("*.tif"))
    print(f"Found {len(tif_files)} tiles.")
    
    # 1. Verify CRS from first tile
    with rasterio.open(tif_files[0]) as src:
        print(f"GBA CRS: {src.crs}")
        if src.crs.to_epsg() != 32640:
            print(f"WARNING: GBA CRS is {src.crs}, expected EPSG:32640. Ensure CSV pixels match this system.")

    for t_idx, t in enumerate(tif_files):
        print(f" Processing Tile {t_idx+1}/{len(tif_files)}: {t.name}")
        
        with rasterio.open(t) as src:
            # Check overlap logic to get pixels in a tile
            tb = src.bounds
            # Pixel center must be left of tile right edge, right of tile left edge, etc.
            # the 375m is there due to the 750m pixel size and the fact that we are checking for overlap of the pixel center and the tile perhaps the pixel centre outside but it still has cverage inside the tile.
            mask = (
                (df['pixel_x'] < tb.right + HALF_RES) & 
                (df['pixel_x'] > tb.left - HALF_RES) &
                (df['pixel_y'] < tb.top + HALF_RES) & 
                (df['pixel_y'] > tb.bottom - HALF_RES)
            )
            
            # Get overlapping pixels whose 750 m region might intersect this tile
            subset_idxs = df.index[mask]
            if len(subset_idxs) == 0:
                continue
                
            print(f"  -> {len(subset_idxs)} overlaps. Loading Tile to RAM...")
            
            # Load Tile
            nodata = src.nodata if src.nodata is not None else -1
            arr = src.read(1)
            
            # Mask low values (Ground noise < 2m) - only focus on buildings
            ground_mask = (arr <= 2.0)
            arr[ground_mask] = nodata
            
            transform = src.transform
            height, width = arr.shape
            
            # Updates
            sums = []
            sums_sq = []
            counts = []
            indices = []
            
            # go through each overlapping pixel
            for idx in tqdm(subset_idxs, desc="  Aggregating", leave=False):
                # Get corresponding pixel_x and pixel_y values from the excel sheet
                px = df.at[idx, 'pixel_x']
                py = df.at[idx, 'pixel_y']
                
                # Geo coords of window - Compute 750m window around the pixel center
                w_left = px - HALF_RES
                w_right = px + HALF_RES
                w_top = py + HALF_RES
                w_bottom = py - HALF_RES
                
                # Convert to Pixel Coords
                # row = (coord_y - origin_y) / pixel_height
                # col = (coord_x - origin_x) / pixel_width
                # rasterio.transform.rowcol is robust
                
                r_start, c_start = rowcol(transform, w_left, w_top)
                r_end, c_end = rowcol(transform, w_right, w_bottom)
                
                # Handle ordering (row indices increase downwards)
                # rowcol returns int
                
                r_min = min(r_start, r_end)
                r_max = max(r_start, r_end)
                c_min = min(c_start, c_end)
                c_max = max(c_start, c_end)
                
                # Clip to array bounds - preventing negative index out of tile
                r_min = max(0, r_min)
                r_max = min(height, r_max)
                c_min = max(0, c_min)
                c_max = min(width, c_max)
                
                # if the window is completly out of bounds with no overlap, skip it
                if r_min >= r_max or c_min >= c_max:
                    continue
                
                # Slice
                # arr[y_index : x_index]
                window_data = arr[r_min:r_max, c_min:c_max]
                
                valid_mask = (window_data != nodata)
                valid_data = window_data[valid_mask]
                
                if valid_data.size > 0:
                    current_sum = np.sum(valid_data)
                    current_sum_sq = np.sum(valid_data ** 2)
                    current_count = valid_data.size
                    
                    # Update global df
                    # Better to collect lists
                    sums.append(current_sum)
                    sums_sq.append(current_sum_sq)
                    counts.append(current_count)
                    indices.append(idx)

            # Bulk Update the dataframe with the data collected
            if indices:
                df.loc[indices, 'gba_height_sum'] += sums
                df.loc[indices, 'gba_height_sum_sq'] += sums_sq
                df.loc[indices, 'gba_pixel_count'] += counts

    # Final Average & Std Dev
    print("Computing Averages and Standard Deviations...")
    # Avoid division by zero
    df['height_mean'] = 0.0
    df['height_std']  = 0.0
    valid_rows = df['gba_pixel_count'] > 0
    
    # E[X] = sum / count
    e_x = df.loc[valid_rows, 'gba_height_sum'] / df.loc[valid_rows, 'gba_pixel_count']
    df.loc[valid_rows, 'height_mean'] = e_x
    
    # E[X^2] = sum_sq / count
    e_x2 = df.loc[valid_rows, 'gba_height_sum_sq'] / df.loc[valid_rows, 'gba_pixel_count']
    
    # Var(X) = E[X^2] - (E[X])^2
    variance = e_x2 - (e_x ** 2)
    # Correct tiny floating point negatives to 0
    variance = variance.clip(lower=0) 
    df.loc[valid_rows, 'height_std'] = np.sqrt(variance)
    
    # Drop temp cols
    df.drop(columns=['gba_height_sum', 'gba_height_sum_sq', 'gba_pixel_count'], inplace=True)
    
    print(f"Saving enriched CSV to: {OUTPUT_CSV_PATH}")
    df.to_csv(OUTPUT_CSV_PATH, index=False)
    
    # Stats
    print("Height Stats:")
    print(df['height_mean'].describe())

if __name__ == "__main__":
    process_gba_ultra_fast()
