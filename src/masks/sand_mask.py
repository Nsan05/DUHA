import rasterio
import numpy as np
import os
from pathlib import Path
import logging

BASE_DIR = Path(__file__).parent.parent.parent
INPUT_DIR = BASE_DIR / "data" / "intermediate" / "sentinel2_30m"
MASK_DIR = BASE_DIR / "data" / "intermediate" / "masks"
OUTPUT_FILE = MASK_DIR / "sand_mask_30m.tif"

# Thresholds
TH_NDWI = -0.07   # Strict Water Exclusion
TH_NDVI = 0.15    # Vegetation Exclusion
TH_BSI = 0.08     # Bare soil index
TH_ALBEDO = 0.25  # Brightness Threshold: Sand is bright, Water is dark

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_sand_mask():
    logger.info("Starting Sand Mask Creation (w/ Albedo)...")
    
    # Paths
    ndvi_path = INPUT_DIR / "ndvi_30m.tif"
    ndwi_path = INPUT_DIR / "ndwi_30m.tif"
    bsi_path = INPUT_DIR / "bsi_30m.tif"
    albedo_path = INPUT_DIR / "albedo_30m.tif"
    urban_path = MASK_DIR / "urban_mask_30m.tif"
    
    # Check existence
    for p in [ndvi_path, ndwi_path, bsi_path, albedo_path, urban_path]:
        if not p.exists():
            logger.error(f"Missing input file: {p}")
            return

    # Load Data
    with rasterio.open(ndvi_path) as src:
        meta = src.meta.copy()
        ndvi = src.read(1)
        
    with rasterio.open(ndwi_path) as src:
        ndwi = src.read(1)
        
    with rasterio.open(bsi_path) as src:
        bsi = src.read(1)

    with rasterio.open(albedo_path) as src:
        albedo = src.read(1)
        
    with rasterio.open(urban_path) as src:
        urban = src.read(1)

    logger.info("Data loaded. Applying logic...")

    # Apply Logic
    # 1. Urban Only
    # 2. Not Water (NDWI)
    # 3. Not Veg (NDVI)
    # 4. Sol/Sand (BSI)
    # 5. Bright (Albedo) -> Filters out dark muddy water
    
    sand_mask = np.zeros_like(ndvi, dtype='uint8')
    
    condition = (
        (urban == 1) & 
        (ndwi < TH_NDWI) & 
        (ndvi < TH_NDVI) & 
        (bsi > TH_BSI) &
        (albedo > TH_ALBEDO)
    )
    
    sand_mask[condition] = 1
    
    # Calculate stats
    total_urban = np.sum(urban == 1)
    total_sand = np.sum(sand_mask == 1)
    logger.info(f"Total Urban Pixels: {total_urban:,}")
    logger.info(f"Identified Sand Pixels: {total_sand:,}")
    if total_urban > 0:
        logger.info(f"Sand Fraction in Urban Area: {total_sand/total_urban*100:.2f}%")

    # Save Output
    meta.update({
        'dtype': 'uint8',
        'count': 1,
        'nodata': 0,
        'compress': 'lzw'
    })
    
    os.makedirs(MASK_DIR, exist_ok=True)
    
    # Safe Delete attempt
    if OUTPUT_FILE.exists():
        try:
            os.remove(OUTPUT_FILE)
        except PermissionError:
             logger.error(f"PERMISSION DENIED: Cannot overwrite {OUTPUT_FILE}. Please close the file in QGIS/ArcGIS and try again.")
             return

    with rasterio.open(OUTPUT_FILE, 'w', **meta) as dst:
        dst.write(sand_mask, 1)
        
    logger.info(f"Sand mask saved to {OUTPUT_FILE}")

if __name__ == "__main__":
    create_sand_mask()
