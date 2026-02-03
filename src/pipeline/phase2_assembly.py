import logging
import sys
from pathlib import Path

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# --- CONFIGURATION ---
BASE_DIR = Path(__file__).parent.parent.parent
PHASE1_DIR = BASE_DIR / "data" / "final" / "phase1_features"
MASKS_DIR = BASE_DIR / "data" / "intermediate" / "masks"
VIIRS_DIR = BASE_DIR / "data" / "raw" / "viirs" / "daytime"
OUTPUT_DIR = BASE_DIR / "data" / "final"
OUTPUT_FILE = OUTPUT_DIR / "phase2_training_table.csv"

# Required Phase 1 Features (30m)
REQUIRED_FEATURES = [
    "ndvi_30m.tif",
    "albedo_30m.tif",
    "building_density_30m.tif",
    "road_density_30m.tif",
    "sand_mask_30m.tif",
]

# Required Masks
REQUIRED_MASKS = [
    "urban_mask_30m.tif",
    "water_mask_full_30m.tif"
]

def validate_environment():
    """
    Step 1: Validate that all input directories and required files exist.
    """
    logger.info("STEP 1: VALIDATING ENVIRONMENT")
    logger.info("-" * 40)
    
    all_valid = True
    
    # Check Directories
    for name, path in [("Phase 1 Features", PHASE1_DIR), 
                       ("Masks", MASKS_DIR), 
                       ("VIIRS Data", VIIRS_DIR)]:
        if path.exists():
            logger.info(f"[OK] Found {name} Directory: {path}")
        else:
            logger.error(f"[FAIL] Missing {name} Directory: {path}")
            all_valid = False

    # Check Required Features
    logger.info("\nChecking Feature Files...")
    if PHASE1_DIR.exists():
        for f in REQUIRED_FEATURES:
            fpath = PHASE1_DIR / f
            if fpath.exists():
                logger.info(f"  [OK] Found {f}")
            else:
                logger.error(f"  [FAIL] Missing Feature: {f}")
                all_valid = False
                
    # Check Required Masks
    logger.info("\nChecking Mask Files...")
    if MASKS_DIR.exists():
        for f in REQUIRED_MASKS:
            fpath = MASKS_DIR / f
            if fpath.exists():
                logger.info(f"  [OK] Found {f}")
            else:
                logger.error(f"  [FAIL] Missing Mask: {f}")
                all_valid = False
            
    # Check VIIRS Data Availability
    logger.info("\nChecking VIIRS Data...")
    if VIIRS_DIR.exists():
        viirs_files = list(VIIRS_DIR.rglob("*.nc"))
        if viirs_files:
            logger.info(f"  [OK] Found {len(viirs_files)} VIIRS NetCDF files.")
        else:
            logger.warning("  [WARN] No .nc files found in VIIRS directory!")
            # Not strictly a fail for code existence, but a fail for execution
            
    logger.info("-" * 40)
    if all_valid:
        logger.info("ENVIRONMENT VALIDATION SUCCESSFUL. Ready for Step 2.")
        return True
    else:
        logger.error("ENVIRONMENT VALIDATION FAILED. Fix missing files.")
        sys.exit(1)

def test_viirs_loading():
    """
    Step 2: Test VIIRS Loading & Geometry.
    """
    logger.info("\nSTEP 2: TESTING VIIRS GEOMETRY")
    logger.info("-" * 40)
    
    # Add BASE_DIR to path for imports
    sys.path.append(str(BASE_DIR))
    try:
        from src.features import viirs
    except ImportError as e:
        logger.error(f"Failed to import src.features.viirs: {e}")
        sys.exit(1)
        
    # Pick first file
    viirs_files = list(VIIRS_DIR.rglob("*.nc"))
    if not viirs_files:
        logger.error("No VIIRS files found.")
        sys.exit(1)
        
    test_file = viirs_files[0]
    logger.info(f"Testing with file: {test_file.name}")
    
    # 1. Load
    data = viirs.load_viirs_scene(test_file)
    logger.info(f"  [OK] Loaded Data. Shape: {data['lst'].shape}")
    logger.info(f"       Lat Range: {data['lat'].min():.4f} to {data['lat'].max():.4f}")
    logger.info(f"       Lon Range: {data['lon'].min():.4f} to {data['lon'].max():.4f}")
    
    # 2. Quality Filter
    clean_lst, valid_mask = viirs.filter_quality(data['lst'], data['qc'])
    valid_count = valid_mask.sum()
    total_count = valid_mask.size
    logger.info(f"  [OK] Quality Filter. Valid Pixels: {valid_count:,} / {total_count:,} ({valid_count/total_count*100:.1f}%)")
    
    # 3. Transform
    xx, yy = viirs.transform_coords(data['lat'], data['lon'])
    logger.info(f"  [OK] Transformed Coords (EPSG:32640).")
    logger.info(f"       X Range: {xx.min():.1f} to {xx.max():.1f}")
    logger.info(f"       Y Range: {yy.min():.1f} to {yy.max():.1f}")
    
    # Save a small verified file for inspection? No, just logging is enough for now.
    logger.info("-" * 40)
    logger.info("VIIRS GEOMETRY EXTRACTION VERIFIED.")

if __name__ == "__main__":
    if validate_environment():
        test_viirs_loading()
