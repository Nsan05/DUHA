
import json
import numpy as np
import rasterio
from rasterio.transform import Affine
import joblib
import lightgbm as lgb
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Paths
DATA_DIR = Path("data/final/phase1_features")
REF_GRID_META = Path("data/intermediate/grids/reference_grid_meta.json")
MODEL_PATH = Path("data/models/gb_model_anomaly.joblib")
OUTPUT_DIR = Path("data/final/phase2_outputs")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_PATH = OUTPUT_DIR / "lst_anomaly_30m.tif"

# Feature rasters in the SAME ORDER as the training features
FEATURE_FILES = {
    'ndvi_mean':                DATA_DIR / "ndvi_30m.tif",
    'ndvi_std':                 DATA_DIR / "ndvi_std_30m.tif",
    'albedo_mean':              DATA_DIR / "albedo_30m.tif",
    'albedo_std':               DATA_DIR / "albedo_std_30m.tif",
    'building_density_mean':    DATA_DIR / "building_density_30m.tif",
    'building_density_std':     DATA_DIR / "building_density_std_30m.tif",
    'height_mean':              DATA_DIR / "height_30m.tif",
    'height_std':               DATA_DIR / "height_std_30m.tif",
    'road_density_mean':        DATA_DIR / "road_density_30m.tif",
    'road_density_std':         DATA_DIR / "road_density_std_30m.tif",
    'sand_mask_fraction':       DATA_DIR / "sand_mask_30m.tif",
    'water_mask_full_fraction': DATA_DIR / "water_mask_full_30m.tif",
    'dist_to_coast_m':          DATA_DIR / "dist_to_coast_30m.tif",
}

def main():
    """
    Phase 2C: Statistical Downscaling
    
    Applies the 750m-trained model at 30m resolution to produce
    a city-wide high-resolution LST anomaly map.
    
    Steps:
    1. Load all 8 feature rasters (30m).
    2. Build a valid-pixel mask (no NoData in any feature).
    3. Run model.predict() on all valid pixels.
    4. Save the output as a GeoTIFF.
    """
    
    # 1. Load reference grid
    logger.info(f"Loading reference grid: {REF_GRID_META}")
    with open(REF_GRID_META) as f:
        meta = json.load(f)
    
    ref_transform = Affine(*meta['transform'])
    ref_crs = meta['crs']
    height = meta['height']
    width = meta['width']
    
    logger.info(f"Grid: {height}x{width}, CRS: {ref_crs}")
    
    # 2. Load all feature rasters
    logger.info(f"Loading {len(FEATURE_FILES)} feature rasters...")
    feature_names = list(FEATURE_FILES.keys())
    # creating a 3D map
    feature_stack = np.zeros((len(feature_names), height, width), dtype=np.float32)
    # Common maks to find valid pixels across all the feature maps
    valid_mask = np.ones((height, width), dtype=bool)
    
    for i, (name, path) in enumerate(FEATURE_FILES.items()):
        logger.info(f"  [{i+1}/{len(FEATURE_FILES)}] {name}: {path.name}")
        
        with rasterio.open(path) as src:
            data = src.read(1).astype(np.float32)
            nodata = src.nodata
            
            # Only NDVI/Albedo and Density/Roads define the study area boundary.
            # Height, Sand, Water, Coast use 0 as a valid value (no buildings, no sand, etc.)
            
            if name.endswith('_std'):
                # Std Dev rasters have NaN where the 750m window had absolutely 0 valid data
                # (e.g., 0 buildings, 0 roads). This means 0 variation. 
                # Do NOT erode the valid_mask. Just fill with 0.
                if nodata is not None and np.isnan(nodata):
                    data[np.isnan(data)] = 0.0
                elif nodata is not None:
                    data[data == nodata] = 0.0
            else:
                # Primary features: define the valid_mask geometry
                if nodata == -9999.0:
                    # NDVI, Albedo: -9999 means outside study area
                    outside = (data <= -9000)
                    valid_mask &= ~outside
                    data[outside] = 0  # Replace sentinel with 0 for model input
                    
                elif nodata is not None and np.isnan(nodata):
                    # Density, Roads: NaN means outside study area
                    outside = np.isnan(data)
                    valid_mask &= ~outside
                    data[outside] = 0
                
                # Height, Sand, Water, Coast: 0 is a VALID value, do NOT mask these
            
            feature_stack[i] = data
    
    n_valid = np.sum(valid_mask)
    n_total = height * width
    logger.info(f"Valid pixels: {n_valid:,} / {n_total:,} ({n_valid/n_total:.1%})")
    
    # 3. Load model
    logger.info(f"Loading model: {MODEL_PATH}")
    model = joblib.load(MODEL_PATH)
    
    # 4. Prepare feature matrix for valid pixels only
    logger.info("Preparing feature matrix for inference...")
    # Extract valid pixels: shape (n_valid, 8)
    valid_rows = valid_mask.ravel()
    X = feature_stack.reshape(len(feature_names), -1).T  # (n_pixels, 8)
    X_valid = X[valid_rows]
    
    logger.info(f"Running inference on {X_valid.shape[0]:,} pixels...")
    
    # 5. Run inference in chunks (to avoid memory issues)
    CHUNK_SIZE = 500_000
    predictions = np.zeros(X_valid.shape[0], dtype=np.float32)
    
    n_chunks = (X_valid.shape[0] + CHUNK_SIZE - 1) // CHUNK_SIZE
    for i in range(n_chunks):
        start = i * CHUNK_SIZE
        end = min((i + 1) * CHUNK_SIZE, X_valid.shape[0])
        predictions[start:end] = model.predict(X_valid[start:end])
        
        if (i + 1) % 10 == 0 or i == n_chunks - 1:
            logger.info(f"  Chunk {i+1}/{n_chunks} done ({end:,} pixels)")
    
    # 6. Reconstruct the output raster
    logger.info("Reconstructing output raster...")
    output = np.full(n_total, np.nan, dtype=np.float32)
    output[valid_rows] = predictions
    output = output.reshape(height, width)
    
    # Stats
    logger.info(f"Prediction Stats:")
    logger.info(f"  Min:  {np.nanmin(output):.2f} K")
    logger.info(f"  Max:  {np.nanmax(output):.2f} K")
    logger.info(f"  Mean: {np.nanmean(output):.2f} K")
    logger.info(f"  Std:  {np.nanstd(output):.2f} K")
    
    # 7. Save GeoTIFF
    out_profile = {
        'driver': 'GTiff',
        'dtype': 'float32',
        'width': width,
        'height': height,
        'count': 1,
        'crs': ref_crs,
        'transform': ref_transform,
        'nodata': np.nan,
        'compress': 'lzw'
    }
    
    logger.info(f"Saving to: {OUTPUT_PATH}")
    with rasterio.open(OUTPUT_PATH, 'w', **out_profile) as dst:
        dst.write(output, 1)
    
    logger.info("Phase 2C Downscaling Complete!")

if __name__ == "__main__":
    main()
