
import numpy as np
import rasterio
from scipy import ndimage
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Paths
WATER_MASK = Path("data/final/phase1_features/water_mask_full_30m.tif")
OUTPUT_PATH = Path("data/final/phase1_features/dist_to_coast_30m.tif")

def main():
    """
    Computes distance-to-coast for every 30m pixel and saves as a GeoTIFF.
    
    Steps:
    1. Load water mask (binary: 0=Land, 1=Water).
    2. Connected Component Labeling to find separate water bodies.
    3. Identify the largest water body (= Persian Gulf).
    4. Compute Euclidean Distance Transform from Gulf coastline.
    5. Save as GeoTIFF aligned to the same grid as other 30m features.
    """
    
    # 1. Load Water Mask
    logger.info(f"Loading water mask: {WATER_MASK}")
    with rasterio.open(WATER_MASK) as src:
        water = src.read(1)
        profile = src.profile.copy()
        pixel_size = src.res[0]  # 30m
    
    logger.info(f"Water mask shape: {water.shape}, Pixel size: {pixel_size}m")
    
    # 2. Connected Component Labeling
    logger.info("Finding connected water bodies...")
    labeled, num_features = ndimage.label(water)
    logger.info(f"Found {num_features} separate water bodies.")
    
    # 3. Find the Largest (= Persian Gulf)
    component_sizes = ndimage.sum(water, labeled, range(1, num_features + 1))
    largest_id = np.argmax(component_sizes) + 1
    largest_size = int(component_sizes[largest_id - 1])
    logger.info(f"Gulf: Label {largest_id}, Size: {largest_size} pixels ({largest_size * pixel_size**2 / 1e6:.1f} km²)")
    
    # 4. Euclidean Distance Transform
    logger.info("Computing Euclidean Distance Transform...")
    gulf_mask = (labeled == largest_id).astype(np.uint8)
    land_mask = 1 - gulf_mask
    distances = ndimage.distance_transform_edt(land_mask, sampling=[pixel_size, pixel_size])
    
    logger.info(f"Distance range: {distances.min():.0f}m to {distances.max():.0f}m")
    
    # 5. Save as GeoTIFF
    out_profile = profile.copy()
    out_profile.update(
        dtype='float32',
        count=1,
        nodata=-1,
        compress='lzw'
    )
    
    logger.info(f"Saving to: {OUTPUT_PATH}")
    with rasterio.open(OUTPUT_PATH, 'w', **out_profile) as dst:
        dst.write(distances.astype(np.float32), 1)
    
    logger.info("Done!")

if __name__ == "__main__":
    main()
