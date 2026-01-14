import rasterio
import numpy as np
import logging
import sys
from pathlib import Path

# Configure Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# STEP 1: CONFIGURATION
# --------------------
BASE_DIR = Path(__file__).parent.parent
NDWI_FILE = BASE_DIR / "data" / "intermediate" / "sentinel2_30m" / "ndwi_30m.tif"
URBAN_MASK_FILE = BASE_DIR / "data" / "intermediate" / "masks" / "urban_mask_30m.tif"
OUTPUT_FILE = BASE_DIR / "data" / "intermediate" / "masks" / "water_mask_30m.tif"

# Scientific Threshold (Open Water > 0.1)
WATER_THRESHOLD = 0.1

def load_urban_mask():
    """
    STEP 2: Load the Urban Boundary Mask.
    Acts as the 'Cookie Cutter' or spatial context.
    """
    logger.info("-" * 40)
    logger.info("LOADING URBAN MASK")
    logger.info("-" * 40)
    
    if not URBAN_MASK_FILE.exists():
        logger.error(f"Urban mask not found at {URBAN_MASK_FILE}")
        sys.exit(1)
        
    with rasterio.open(URBAN_MASK_FILE) as src:
        # Read as boolean/binary
        data = src.read(1)
        profile = src.profile
        
        # Valid Urban Area = 1
        # We ensure it's treated as a boolean mask
        urban_bool = (data == 1)
        
        count = np.sum(urban_bool)
        logger.info(f"Urban Mask Loaded. Dimensions: {data.shape}")
        logger.info(f"Urban Pixels: {count:,} (Area inside boundary)")
        
        return urban_bool, profile

def generate_water_candidates():
    """
    STEP 3: Load NDWI and Threshold.
    Identifies 'Physically Water' pixels purely based on spectral signal.
    """
    logger.info("-" * 40)
    logger.info(f"THRESHOLDING NDWI (Threshold: {WATER_THRESHOLD})")
    logger.info("-" * 40)
    
    if not NDWI_FILE.exists():
        logger.error(f"NDWI file not found at {NDWI_FILE}")
        sys.exit(1)
        
    with rasterio.open(NDWI_FILE) as src:
        ndwi = src.read(1)
        
        # Create Binary Mask: 1 where Water, 0 where Land
        # Logic: NDWI >= 0.1
    
        # Suppress RuntimeWarning for NaN comparisons
        with np.errstate(invalid='ignore'):
            water_candidates = (ndwi >= WATER_THRESHOLD)
            
        water_count = np.sum(water_candidates)
        total_pixels = ndwi.size
        
        logger.info(f"NDWI Loaded. Dimensions: {ndwi.shape}")
        logger.info(f"Water Candidates Detected: {water_count:,} ({water_count/total_pixels*100:.2f}% of total grid)")
        
        return water_candidates

if __name__ == "__main__":
    # Execute Step 2 & 3
    urban_mask, profile = load_urban_mask()
    water_candidates = generate_water_candidates()
