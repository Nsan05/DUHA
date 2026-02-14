import pandas as pd
import numpy as np
import rasterio
from rasterio.transform import rowcol
from scipy import ndimage
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Paths
DATA_DIR = Path("data")
WATER_MASK = DATA_DIR / "final/phase1_features/water_mask_full_30m.tif"
CSV_PATH = DATA_DIR / "final/phase2_training_table_enriched.csv"
OUTPUT_CSV = DATA_DIR / "final/phase2_training_table_enriched.csv"  # Overwrite with new column

def compute_coast_distance():
    """
    Computes distance-to-coast for each training pixel.
    
    Steps:
    1. Load water mask (binary: 0=Land, 1=Water).
    2. Connected Component Labeling to find separate water bodies.
    3. Identify the largest water body (= Persian Gulf).
    4. Compute Euclidean Distance Transform from Gulf coastline.
    5. Sample distance at each training pixel location.
    """
    
    # 1. Load Water Mask
    logger.info(f"Loading water mask: {WATER_MASK}")
    with rasterio.open(WATER_MASK) as src:
        water = src.read(1)  # shape: (rows, cols), values: 0 or 1
        transform = src.transform
        pixel_size = src.res[0]  # 30m
    
    logger.info(f"Water mask shape: {water.shape}, Pixel size: {pixel_size}m")
    
    # 2. Connected Component Labeling
    # Find all separate water bodies
    logger.info("Finding connected water bodies...")
    labeled, num_features = ndimage.label(water)
    logger.info(f"Found {num_features} separate water bodies.")
    
    # 3. Find the Largest (= Persian Gulf)
    # Count pixels in each component
    component_sizes = ndimage.sum(water, labeled, range(1, num_features + 1))
    largest_id = np.argmax(component_sizes) + 1  # +1 because labels start at 1
    largest_size = int(component_sizes[largest_id - 1])
    
    logger.info(f"Largest water body (Gulf): Label {largest_id}, Size: {largest_size} pixels ({largest_size * pixel_size**2 / 1e6:.1f} km²)")
    
    # 4. Create Gulf-Only Mask - Changes all the pixels that are not the largest water body to 0
    gulf_mask = (labeled == largest_id).astype(np.uint8)
    
    # 5. Euclidean Distance Transform
    # distance_transform_edt computes distance from every 0-pixel to the nearest 1-pixel
    # We want distance from land to Gulf, so we invert: land=0, gulf=1 -> dist from 0 to 1
    # Actually, edt computes distance from 0 to nearest non-zero
    # We want: for each land pixel, how far is the nearest Gulf pixel?
    # So input should be: 0 where Gulf is, 1 where land is -> edt gives dist from Gulf
    
    logger.info("Computing Euclidean Distance Transform (this may take a moment)...")
    # Invert: Gulf=0 (source), Land=1 (compute distance for these) - for every non zeo pixel how far is nearest gulf pixel
    land_mask = 1 - gulf_mask
    distances = ndimage.distance_transform_edt(land_mask, sampling=[pixel_size, pixel_size]) # sampling is done to communicte the fact that each pixel is not 1m but 30m
    
    logger.info(f"Distance range: {distances.min():.0f}m to {distances.max():.0f}m")
    
    # 6. Sample at Training Pixel Locations
    logger.info(f"Loading CSV: {CSV_PATH}")
    df = pd.read_csv(CSV_PATH)
    
    coast_distances = []
    for idx, row in df.iterrows():
        px = row['pixel_x']
        py = row['pixel_y']
        
        # Convert UTM coords to raster row/col - in the 30m grid
        r, c = rowcol(transform, px, py)
        
        # Bounds check
        if 0 <= r < distances.shape[0] and 0 <= c < distances.shape[1]:
            coast_distances.append(distances[r, c])
        else:
            coast_distances.append(np.nan)
    
    df['dist_to_coast_m'] = coast_distances
    
    # Stats
    logger.info("Distance to Coast Stats:")
    logger.info(f"  Min:  {df['dist_to_coast_m'].min():.0f} m")
    logger.info(f"  Max:  {df['dist_to_coast_m'].max():.0f} m")
    logger.info(f"  Mean: {df['dist_to_coast_m'].mean():.0f} m")
    logger.info(f"  NaN:  {df['dist_to_coast_m'].isna().sum()}")
    
    # 7. Save
    logger.info(f"Saving to: {OUTPUT_CSV}")
    df.to_csv(OUTPUT_CSV, index=False)
    
    logger.info("Done!")

if __name__ == "__main__":
    compute_coast_distance()
