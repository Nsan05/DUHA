"""
Generate Standard Deviation Rasters (Sliding 25x25 Window)

For each continuous 30m feature raster, this script computes the local
standard deviation using a 25x25 pixel window (750m) centered on each pixel.

This gives every 30m pixel a "neighborhood texture" value that matches
how the model was trained (aggregation.py computes std over the same window).

Input:  ndvi_30m.tif, albedo_30m.tif, building_density_30m.tif, 
        road_density_30m.tif, height_30m.tif
Output: ndvi_std_30m.tif, albedo_std_30m.tif, building_density_std_30m.tif,
        road_density_std_30m.tif, height_std_30m.tif
"""

import numpy as np
import rasterio
from pathlib import Path
from scipy.ndimage import uniform_filter
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Paths
FEATURES_DIR = Path("data/final/phase1_features")

# The 5 continuous features that need _std rasters
# Format: (input_filename, output_filename)
RASTER_PAIRS = [
    ("ndvi_30m.tif",              "ndvi_std_30m.tif"),
    ("albedo_30m.tif",            "albedo_std_30m.tif"),
    ("building_density_30m.tif",  "building_density_std_30m.tif"),
    ("road_density_30m.tif",      "road_density_std_30m.tif"),
    ("height_30m.tif",            "height_std_30m.tif"),
]

# Window size: 25x25 pixels = 750m at 30m resolution
WINDOW_SIZE = 25

def compute_local_std(data, window_size, nodata_val=None):
    """
    Computes local standard deviation using a sliding window.
    
    Uses the mathematical identity:
        Std(X) = sqrt( E[X^2] - E[X]^2 )
    
    This avoids looping over every pixel and uses fast convolution instead.
    
    Args:
        data: 2D numpy array of the raster values
        window_size: Size of the square window (e.g., 25 for 750m)
        nodata_val: NoData value to mask out
        
    Returns:
        2D numpy array of local standard deviations
    """
    
    # Create a float copy and mask NoData
    arr = data.astype(np.float64)
    
    # invalid pixels are set to 0
    if nodata_val is not None:
        if np.isnan(nodata_val):
            mask = np.isnan(arr)
        else:
            mask = (arr == nodata_val) | (arr <= -9000) # no data poisitons are marked as true
        arr[mask] = 0.0
    else:
        mask = np.zeros_like(arr, dtype=bool)
    
    # Count of valid pixels in each window
    valid = (~mask).astype(np.float64)
    # filter returns mean and to get sum, multiply by number of pixels in window
    count = uniform_filter(valid, size=window_size, mode='constant', cval=0.0) * (window_size ** 2)
    
    # E[X] = mean of valid values in window
    mean_x = uniform_filter(arr * valid, size=window_size, mode='constant', cval=0.0) * (window_size ** 2)
    
    # E[X^2] = mean of squared values in window  
    mean_x2 = uniform_filter((arr ** 2) * valid, size=window_size, mode='constant', cval=0.0) * (window_size ** 2)
    
    # Avoid division by zero
    safe_count = np.maximum(count, 1.0)
    
    # Var(X) = E[X^2] - (E[X])^2  (using sums / count)
    variance = (mean_x2 / safe_count) - (mean_x / safe_count) ** 2
    
    # Correct tiny floating point negatives
    variance = np.maximum(variance, 0.0)
    
    std_dev = np.sqrt(variance)
    
    # Set areas with no valid data back to NaN
    std_dev[count < 1] = np.nan
    
    return std_dev.astype(np.float32)


def main():
    logger.info("=" * 50)
    logger.info("GENERATING STANDARD DEVIATION RASTERS")
    logger.info("=" * 50)
    logger.info(f"Window Size: {WINDOW_SIZE}x{WINDOW_SIZE} pixels (750m)")
    
    for input_name, output_name in RASTER_PAIRS:
        input_path = FEATURES_DIR / input_name
        output_path = FEATURES_DIR / output_name
        
        if not input_path.exists():
            logger.warning(f"MISSING: {input_path} - Skipping.")
            continue
        
        logger.info(f"Processing: {input_name} -> {output_name}")
        
        with rasterio.open(input_path) as src:
            data = src.read(1)
            nodata = src.nodata
            profile = src.profile.copy()
            
            logger.info(f"  Shape: {data.shape}, NoData: {nodata}")
            
            # Compute local std dev
            std_raster = compute_local_std(data, WINDOW_SIZE, nodata_val=nodata)
            
            # Stats
            valid_std = std_raster[~np.isnan(std_raster)]
            if valid_std.size > 0:
                logger.info(f"  Std Dev Stats -> Min: {valid_std.min():.4f}, Max: {valid_std.max():.4f}, Mean: {valid_std.mean():.4f}")
            
            # Save output with same georeferencing
            profile.update(dtype='float32', nodata=np.nan)
            
            with rasterio.open(output_path, 'w', **profile) as dst:
                dst.write(std_raster, 1)
            
            logger.info(f"  Saved: {output_path}")
    
    logger.info("=" * 50)
    logger.info("ALL STD RASTERS GENERATED!")
    logger.info("=" * 50)


if __name__ == "__main__":
    main()
