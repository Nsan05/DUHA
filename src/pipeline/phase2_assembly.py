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
    
    return data, xx, yy

def test_aggregation(viirs_data, xx, yy):
    """
    Step 3: Test Aggregation on a single pixel.
    """
    logger.info("\nSTEP 3: TESTING AGGREGATION LOGIC")
    logger.info("-" * 40)
    
    try:
        from src.features import aggregation
    except ImportError as e:
        logger.error(f"Failed to import src.features.aggregation: {e}")
        sys.exit(1)
        
    import rasterio
    import numpy as np
    
    # Open Raster Handles
    # We need to Keep them open.
    raster_handles = {}
    
    # 1. Open Urban Mask
    urban_path = MASKS_DIR / "urban_mask_30m.tif"
    if not urban_path.exists():
        logger.error("Urban mask not found for test!")
        return
        
    urban_src = rasterio.open(urban_path)
    raster_handles["urban_mask_30m.tif"] = urban_src
    
    # 2. Open one feature (NDVI)
    ndvi_path = PHASE1_DIR / "ndvi_30m.tif"
    if ndvi_path.exists():
        raster_handles["ndvi_30m.tif"] = rasterio.open(ndvi_path)
    
    try:
        # TARGETED SEARCH
        # Intead of blind search, use the Urban Mask metadata to clear target.
        # Urban Mask bounds in EPSG:32640
        mask_bounds = urban_src.bounds
        min_x, max_x = mask_bounds.left, mask_bounds.right
        min_y, max_y = mask_bounds.bottom, mask_bounds.top # Rasterio bounds
        
        logger.info(f"Urban Mask Bounds: X[{min_x:.0f}, {max_x:.0f}], Y[{min_y:.0f}, {max_y:.0f}]")
        
        # Filter VIIRS pixels that fall within these bounds
        # xx, yy are arrays of coordinates for every VIIRS pixel
        
        # Create a mask of VIIRS pixels inside the Urban Mask Box
        spatial_mask = (xx >= min_x) & (xx <= max_x) & (yy >= min_y) & (yy <= max_y)
        
        valid_indices = np.argwhere(spatial_mask)
        
        if valid_indices.size == 0:
             logger.warning("No VIIRS pixels fall within the Urban Mask bounds!")
             return
             
        logger.info(f"Found {len(valid_indices)} VIIRS pixels strictly within Urban Mask bounding box.")
        
        # Test a subset of these
        # Stride to get a spread. Try every 100th pixel to be more thorough but not too slow.
        stride = 100 
        found_count = 0
        
        logger.info(f"Scanning subset of {len(valid_indices)} pixels with stride {stride}...")
        
        for i in range(0, len(valid_indices), stride):
            idx_y, idx_x = valid_indices[i]
            
            vx = xx[idx_y, idx_x]
            vy = yy[idx_y, idx_x]
            
            # Aggregate
            try:
                result = aggregation.aggregate_pixel(vx, vy, raster_handles)
            except Exception as e:
                logger.error(f"Error aggregating pixel ({vx}, {vy}): {e}")
                continue
            
            if result is not None:
                logger.info(f"  [FOUND] Valid Pixel at Index ({idx_y}, {idx_x})")
                logger.info(f"          Coords: ({vx:.1f}, {vy:.1f})")
                logger.info(f"          Urban Fraction: {result['urban_fraction']:.2f}")
                if 'ndvi_mean' in result:
                    logger.info(f"          NDVI Mean (Urban Only): {result['ndvi_mean']:.4f}")
                
                found_count += 1
                found_valid = True
                
                # Stop after finding 3 valid examples to keep logs clean
                if found_count >= 3:
                    break
        
        if not found_valid:
             logger.warning("Checked pixels inside bounds but none met Urban Fraction > 0.3 criteria.")
            
    finally:
        # Close handles
        for src in raster_handles.values():
            src.close()
            
    logger.info("-" * 40)
    logger.info("AGGREGATION LOGIC VERIFIED.")

if __name__ == "__main__":
    if validate_environment():
        data, xx, yy = test_viirs_loading()
        test_aggregation(data, xx, yy)
