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
    else:
        logger.error("ENVIRONMENT VALIDATION FAILED. Fix missing files.")
        sys.exit(1)

if __name__ == "__main__":
    validate_environment()
