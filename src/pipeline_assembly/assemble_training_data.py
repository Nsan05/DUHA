import logging
import sys
import pandas as pd
import numpy as np
import rasterio
from pathlib import Path
from tqdm import tqdm

# Import Project Modules
sys.path.append(str(Path(__file__).parent.parent.parent))
from src.features import viirs, aggregation

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("phase2_assembly.log")
    ]
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
FEATURE_FILES = [
    "ndvi_30m.tif",
    "albedo_30m.tif",
    "building_density_30m.tif",
    "road_density_30m.tif",
    "sand_mask_30m.tif",
    "water_mask_full_30m.tif"
]

def process_viirs_scene(nc_path, raster_handles, urban_src):
    """
    Processes a single VIIRS NetCDF file.
    
    Args:
        nc_path: Path to .nc file.
        raster_handles: Dictionary of open rasterio handles for features.
        urban_src: Open rasterio handle for Urban Mask (for bounding box check).
        
    Returns:
        pd.DataFrame: DataFrame containing valid training samples from this scene.
    """
    scene_name = nc_path.name
    
    # 1. Load VIIRS Data
    try:
        data = viirs.load_viirs_scene(nc_path)
    except Exception as e:
        logger.error(f"Failed to load {scene_name}: {e}")
        return pd.DataFrame()
        
    # 2. Quality Filter (Bit 0-1 check)
    clean_lst, qc_mask = viirs.filter_quality(data['lst'], data['qc'])
    
    # Early exit if too few valid pixels? (Optional, but keeps speed up)
    if qc_mask.sum() == 0:
        logger.warning(f"No valid pixels in {scene_name} after QC.")
        return pd.DataFrame()

    # 3. Transform Coordinates
    # We only care about pixels passed QC? 
    # Transforms entire array efficiently
    xx, yy = viirs.transform_coords(data['lat'], data['lon'])
    
    # 4. Spatial Optimisation (The "Red Box")
    # Bounds of Urban Mask
    mask_bounds = urban_src.bounds
    min_x, max_x = mask_bounds.left, mask_bounds.right
    min_y, max_y = mask_bounds.bottom, mask_bounds.top 
    
    # Create Spatial Mask: Inside Study Area Box
    in_box_mask = (xx >= min_x) & (xx <= max_x) & (yy >= min_y) & (yy <= max_y)
    
    # Combine: Must be (Good Quality) AND (Inside Box)
    final_mask = qc_mask & in_box_mask
    
    valid_indices = np.argwhere(final_mask)
    
    if valid_indices.size == 0:
        return pd.DataFrame() # Scene is outside Dubai
        
    # 5. Aggregate Loop ("The Grey City Check")
    records = []
    
    # Loop over valid pixels
    # Using tqdm just for this scene might be noisy if we loop many scenes.
    # We'll just iterate quietly.
    
    for idx_y, idx_x in valid_indices:
        vx = xx[idx_y, idx_x]
        vy = yy[idx_y, idx_x]
        lst_val = clean_lst[idx_y, idx_x]
        
        # Aggregate Features
        # This checks "Is it actually urban?" (Urban Fraction > 0.3)
        try:
            agg_results = aggregation.aggregate_pixel(vx, vy, raster_handles)
        except Exception:
            continue
            
        if agg_results:
            # Add Target and Metadata
            agg_results['viirs_lst'] = lst_val
            agg_results['scene_id'] = scene_name
            agg_results['pixel_x'] = vx
            agg_results['pixel_y'] = vy
            records.append(agg_results)
            
    return pd.DataFrame(records)

def main():
    logger.info("PHASE 2A: ASSEMBLY STARTED")
    logger.info("-" * 40)
    
    if not OUTPUT_DIR.exists():
        OUTPUT_DIR.mkdir(parents=True)
        
    # 1. Setup Raster Handles
    # We open them ONCE here and keep them open for the whole job.
    # This is much faster than opening/closing per pixel.
    
    raster_handles = {}
    
    try:
        # Open Urban Mask (Critical)
        urban_path = MASKS_DIR / "urban_mask_30m.tif"
        if not urban_path.exists():
            logger.error("Urban mask missing.")
            sys.exit(1)
            
        urban_src = rasterio.open(urban_path)
        raster_handles["urban_mask_30m.tif"] = urban_src
        
        # Open Features
        for fname in FEATURE_FILES:
            fpath = PHASE1_DIR / fname
            if not fpath.exists():
                # Allow creating handles for masks in MASKS_DIR too if needed?
                # The FEATURE_FILES list assumes they are in PHASE1_DIR.
                # Check MASKS_DIR fallback
                if (MASKS_DIR / fname).exists():
                     fpath = MASKS_DIR / fname
                else:
                    logger.warning(f"Feature file missing: {fname} - Skipping.")
                    continue
            
            raster_handles[fname] = rasterio.open(fpath)
            
        # 2. Find VIIRS Files
        viirs_files = list(VIIRS_DIR.rglob("*.nc"))
        logger.info(f"Found {len(viirs_files)} VIIRS files to process.")
        
        all_data = []
        
        # 3. Main Loop
        with tqdm(total=len(viirs_files), desc="Processing Scenes") as pbar:
            for nc_file in viirs_files:
                df = process_viirs_scene(nc_file, raster_handles, urban_src)
                
                if not df.empty:
                    all_data.append(df)
                    pbar.set_postfix({"samples": sum(len(x) for x in all_data)})
                
                pbar.update(1)
                
        # 4. Save
        if all_data:
            final_df = pd.concat(all_data, ignore_index=True)
            logger.info("-" * 40)
            logger.info(f"Assembly Complete. Total Samples: {len(final_df):,}")
            
            final_df.to_csv(OUTPUT_FILE, index=False)
            logger.info(f"Saved to: {OUTPUT_FILE}")
            
            # Simple Stat Check
            logger.info("\nColumns Created:")
            logger.info(final_df.columns.tolist())
            logger.info(f"Average LST: {final_df['viirs_lst'].mean():.2f} K")
            
        else:
            logger.warning("No valid training samples generated!")
            
    except Exception as e:
        logger.error(f"Critical Failure: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Cleanup
        logger.info("Closing file handles...")
        for src in raster_handles.values():
            src.close()

if __name__ == "__main__":
    main()
