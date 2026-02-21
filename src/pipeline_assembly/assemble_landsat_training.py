import pandas as pd
import numpy as np
import rasterio
from rasterio.warp import reproject, Resampling
from rasterio.transform import Affine
from pathlib import Path
import json
import logging
import sys

sys.path.append(str(Path(__file__).parent.parent.parent))
from src.features import landsat

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent.parent.parent
PHASE1_DIR = BASE_DIR / "data" / "final" / "phase1_features"
MASKS_DIR = BASE_DIR / "data" / "intermediate" / "masks"
LANDSAT_DIR = BASE_DIR / "data" / "raw" / "landsat" / "lst"
OUTPUT_DIR = BASE_DIR / "data" / "final"
OUTPUT_FILE = OUTPUT_DIR / "phase3a_training_table.csv"
REF_GRID_META = BASE_DIR / "data" / "intermediate" / "grids" / "reference_grid_meta.json"

FEATURE_FILES = {
    'ndvi_mean':                PHASE1_DIR / "ndvi_30m.tif",
    'albedo_mean':              PHASE1_DIR / "albedo_30m.tif",
    'building_density_mean':    PHASE1_DIR / "building_density_30m.tif",
    'height_mean':              PHASE1_DIR / "height_30m.tif",
    'road_density_mean':        PHASE1_DIR / "road_density_30m.tif",
    'sand_mask_fraction':       PHASE1_DIR / "sand_mask_30m.tif",
    'water_mask_full_fraction': PHASE1_DIR / "water_mask_full_30m.tif",
    'dist_to_coast_m':          PHASE1_DIR / "dist_to_coast_30m.tif",
}

def main():
    logger.info("PHASE 3A: LANDSAT ASSEMBLY STARTED")
    
    with open(REF_GRID_META) as f:
        meta = json.load(f)
        
    ref_transform = Affine(*meta['transform'])
    ref_crs = meta['crs']
    height = meta['height']
    width = meta['width']
    
    # 1. Load Urban Mask
    urban_path = MASKS_DIR / "urban_mask_30m.tif"
    if not urban_path.exists():
        logger.error(f"Missing urban mask: {urban_path}")
        return
        
    with rasterio.open(urban_path) as src:
        urban_mask = src.read(1)
        
    base_valid = (urban_mask == 1)
    
    # 2. Load Features
    feature_stack = {}
    for name, path in FEATURE_FILES.items():
        if not path.exists():
            logger.error(f"Missing feature file: {path}")
            return
            
        with rasterio.open(path) as src:
            data = src.read(1).astype(np.float32)
            nodata = src.nodata
            
            if nodata == -9999.0:
                # captures floating point errors for 9999 and used 9000 as a safety net.
                outside = (data <= -9000)
                base_valid &= ~outside
                data[outside] = 0
            elif nodata is not None and np.isnan(nodata):
                outside = np.isnan(data)
                base_valid &= ~outside
                data[outside] = 0
                
            feature_stack[name] = data
            
    # Calculate X and Y coordinate for each pixel
    logger.info("Generating pixel coordinates...")
    # preparing meshgrid for transform
    cols, rows = np.meshgrid(np.arange(width), np.arange(height))
    # Getting real world coordinate values for each pixel
    xs, ys = rasterio.transform.xy(ref_transform, rows.flatten(), cols.flatten())
    # Reshaping the coordinate values to 2D arrays to match up with the feature arrays
    xs_2d = np.array(xs).reshape(height, width).astype(np.float32)
    ys_2d = np.array(ys).reshape(height, width).astype(np.float32)
    
    # 3. Process Landsat Scenes
    landsat_scenes = [d for d in LANDSAT_DIR.iterdir() if d.is_dir()]
    logger.info(f"Found {len(landsat_scenes)} Landsat scenes to process.")
    
    all_dfs = []
    
    for scene_dir in sorted(landsat_scenes):
        res = landsat.load_landsat_scene(scene_dir)
        if not res:
            continue
            
        lst_data = res['lst']
        src_transform = res['transform']
        src_crs = res['crs']
        
        # Reproject to reference grid
        lst_reproj = np.full((height, width), np.nan, dtype=np.float32)
        reproject(
            source=lst_data,
            destination=lst_reproj,
            src_transform=src_transform,
            src_crs=src_crs,
            dst_transform=ref_transform,
            dst_crs=ref_crs,
            resampling=Resampling.nearest
        )
        
        # Valid pixels for this scene
        valid = base_valid & ~np.isnan(lst_reproj) & (lst_reproj > 0)
        
        if np.sum(valid) == 0:
            logger.warning(f"  No valid urban pixels for {res['scene_id']}")
            continue
            
        # Extract features
        valid_idx = np.where(valid)
        
        scene_df = pd.DataFrame({
            'pixel_x': xs_2d[valid_idx],
            'pixel_y': ys_2d[valid_idx],
            'scene_id': res['scene_id'],
            'landsat_lst': lst_reproj[valid_idx]
        })
        
        for name in FEATURE_FILES.keys():
            scene_df[name] = feature_stack[name][valid_idx]
            
        all_dfs.append(scene_df)
        logger.info(f"  Extracted {len(scene_df):,} samples from {res['scene_id']}")
        
    if all_dfs:
        final_df = pd.concat(all_dfs, ignore_index=True)
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        final_df.to_csv(OUTPUT_FILE, index=False)
        logger.info("-" * 40)
        logger.info(f"Assembly Complete. Total Samples: {len(final_df):,}")
        logger.info(f"Average Landsat LST: {final_df['landsat_lst'].mean():.2f} K")
        logger.info(f"Saved to: {OUTPUT_FILE}")
    else:
        logger.error("No valid data extracted!")

if __name__ == "__main__":
    main()
