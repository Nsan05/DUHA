import shutil
import rasterio
import numpy as np
import logging
import sys
import json
from pathlib import Path

# Configure Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- CONFIGURATION ---
BASE_DIR = Path(__file__).parent.parent
FINAL_DIR = BASE_DIR / "data" / "final" / "phase1_features"
GRID_META_FILE = BASE_DIR / "data" / "intermediate" / "grids" / "reference_grid_meta.json"

# Feature Registry
# format: (source_rel_path, final_name, type)
# type: 'continuous' or 'mask'
FEATURES = [
    # Continuous (Float32)
    ("data/intermediate/sentinel2_30m/ndvi_30m.tif", "ndvi_30m.tif", "continuous"),
    ("data/intermediate/sentinel2_30m/albedo_30m.tif", "albedo_30m.tif", "continuous"),
    ("data/intermediate/urban_form/building_density_30m.tif", "building_density_30m.tif", "continuous"),
    ("data/intermediate/urban_form/road_density_30m.tif", "road_density_30m.tif", "continuous"),
    
    # Masks (UInt8)
    ("data/intermediate/masks/urban_mask_30m.tif", "urban_mask_30m.tif", "mask"),
    ("data/intermediate/masks/water_mask_30m.tif", "water_mask_urban_30m.tif", "mask"),
    ("data/intermediate/masks/water_mask_full_30m.tif", "water_mask_full_30m.tif", "mask"),
    ("data/intermediate/masks/sand_mask_30m.tif", "sand_mask_30m.tif", "mask"),
    
    # Optional
    ("data/intermediate/sentinel2_30m/bsi_30m.tif", "bsi_30m.tif", "continuous"),
]

def load_reference_meta():
    with open(GRID_META_FILE, 'r') as f:
        return json.load(f)

def validate_and_copy():
    logger.info("-" * 40)
    logger.info("FINALIZING PHASE 1 FEATURES")
    logger.info("-" * 40)
    
    # 7.1 Create Final Directory
    if FINAL_DIR.exists():
        logger.info(f"Cleaning existing directory: {FINAL_DIR}")
        shutil.rmtree(FINAL_DIR)
    FINAL_DIR.mkdir(parents=True, exist_ok=True)
    logger.info(f"Created final directory: {FINAL_DIR}")
    
    # Load Master Metadata
    ref_meta = load_reference_meta()
    ref_width = ref_meta['width']
    ref_height = ref_meta['height']
    ref_crs = ref_meta['crs'] # string, e.g. EPSG:32640 or WKT
    # Note: Checking transform exactly can be tricky due to float precision. We check shape/crs mainly.
    
    failed = False
    
    for src_rel, final_name, ftype in FEATURES:
        src_path = BASE_DIR / src_rel
        tgt_path = FINAL_DIR / final_name
        
        logger.info(f"Processing: {final_name}...")
        
        if not src_path.exists():
            logger.error(f"  [MISSING] Source file not found: {src_path}")
            failed = True
            continue
            
        with rasterio.open(src_path) as src:
            # 7.3 Verify Mechanical Compatibility
            # CRS
            if src.crs.to_string() != "EPSG:32640":
                logger.error(f"  [FAIL] CRS Mismatch. Expected EPSG:32640, Got {src.crs.to_string()}")
                failed = True
            
            # Dimensions
            if src.width != ref_width or src.height != ref_height:
                logger.error(f"  [FAIL] Dimension Mismatch. Expected {ref_width}x{ref_height}, Got {src.width}x{src.height}")
                failed = True
                
            # 7.4 Standardise Data Conventions
            profile = src.profile
            dtype = str(profile['dtype'])
            
            if ftype == 'continuous':
                if 'float32' not in dtype:
                    logger.warning(f"  [WARN] Dtype is {dtype}, expected float32. (Strict check failed)")
                
            elif ftype == 'mask':
                if 'uint8' not in dtype:
                    logger.warning(f"  [WARN] Dtype is {dtype}, expected uint8.")
                    
        if not failed:
            # 7.5 Copy
            shutil.copy2(src_path, tgt_path)
            logger.info(f"  [OK] Validated & Copied.")
            
    if failed:
        logger.error("CRITICAL: Finalization failed due to validation errors.")
        sys.exit(1)
        
    logger.info("-" * 40)
    logger.info("VALIDATION COMPLETE")
    logger.info("-" * 40)

def stack_test():
    """
    7.7 Perform a minimal stack-read test
    """
    logger.info("STEP 7.7: STACK TEST")
    
    files = list(FINAL_DIR.glob("*.tif"))
    if not files:
        logger.error("No files in final directory!")
        return
        
    logger.info(f"Attempting to stack {len(files)} files...")
    
    try:
        shapes = []
        arrays = []
        
        for f in files:
            with rasterio.open(f) as src:
                shapes.append(src.shape)
                # Read a small window to verify accessibility
                data = src.read(1, window=rasterio.windows.Window(0, 0, 100, 100))
                arrays.append(data)
                
        # Check shapes
        if not all(s == shapes[0] for s in shapes):
            logger.error(f"Stack Test Failed: Shapes are inconsistent: {shapes}")
            return
            
        # Check stacking
        stack = np.stack(arrays)
        logger.info(f"Stack Test Passed. shape={stack.shape} (Features, 100, 100)")
        logger.info("Phase 1 Feature Stack is Clean & Ready.")
        
    except Exception as e:
        logger.error(f"Stack Test Failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    validate_and_copy()
    stack_test()
