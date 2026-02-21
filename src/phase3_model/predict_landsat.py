import json
import numpy as np
import rasterio
from rasterio.transform import Affine
import joblib
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Paths
DATA_DIR = Path("data/final/phase1_features")
REF_GRID_META = Path("data/intermediate/grids/reference_grid_meta.json")
MODEL_PATH = Path("data/models/gb_model_landsat.joblib")
OUTPUT_DIR = Path("data/final/phase3a_outputs")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_PATH = OUTPUT_DIR / "lst_anomaly_landsat_30m.tif"

# Feature rasters in the SAME ORDER as the training features
FEATURE_FILES = {
    'ndvi_mean':                DATA_DIR / "ndvi_30m.tif",
    'albedo_mean':              DATA_DIR / "albedo_30m.tif",
    'building_density_mean':    DATA_DIR / "building_density_30m.tif",
    'height_mean':              DATA_DIR / "height_30m.tif",
    'road_density_mean':        DATA_DIR / "road_density_30m.tif",
    'sand_mask_fraction':       DATA_DIR / "sand_mask_30m.tif",
    'water_mask_full_fraction': DATA_DIR / "water_mask_full_30m.tif",
    'dist_to_coast_m':          DATA_DIR / "dist_to_coast_30m.tif",
}

def main():
    """
    Phase 3A: Landsat Prediction
    
    Applies the Landsat-trained model at 30m resolution to produce
    a city-wide high-resolution LST anomaly map for the 10:30 AM slot.
    """
    if not MODEL_PATH.exists():
        logger.error(f"Model not found: {MODEL_PATH}")
        return
        
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
    logger.info("Loading 8 feature rasters...")
    feature_names = list(FEATURE_FILES.keys())
    
    feature_stack = np.zeros((len(feature_names), height, width), dtype=np.float32)
    valid_mask = np.ones((height, width), dtype=bool)
    
    for i, (name, path) in enumerate(FEATURE_FILES.items()):
        logger.info(f"  [{i+1}/8] {name}: {path.name}")
        
        with rasterio.open(path) as src:
            data = src.read(1).astype(np.float32)
            nodata = src.nodata
            
            if nodata == -9999.0:
                outside = (data <= -9000)
                valid_mask &= ~outside
                data[outside] = 0
            elif nodata is not None and np.isnan(nodata):
                outside = np.isnan(data)
                valid_mask &= ~outside
                data[outside] = 0
            
            feature_stack[i] = data
    
    # Also load the urban mask to ensure we only predict over urban areas
    # (Consistent with training data assembly)
    urban_mask_path = Path("data/intermediate/masks/urban_mask_30m.tif")
    if urban_mask_path.exists():
        logger.info(f"  [+] Applying urban mask from: {urban_mask_path.name}")
        with rasterio.open(urban_mask_path) as src:
            urban_data = src.read(1)
            valid_mask &= (urban_data == 1)
            
    n_valid = np.sum(valid_mask)
    n_total = height * width
    logger.info(f"Valid urban pixels: {n_valid:,} / {n_total:,} ({n_valid/n_total:.1%})")
    
    # 3. Load model
    logger.info(f"Loading model: {MODEL_PATH}")
    model = joblib.load(MODEL_PATH)
    
    # 4. Prepare feature matrix for valid pixels only
    logger.info("Preparing feature matrix for inference...")
    # flatten the rows and columns into a single row
    valid_rows = valid_mask.ravel()
    # we change to (8, H*W)
    # then we transpose to (H*W, 8)
    X = feature_stack.reshape(len(feature_names), -1).T
    X_valid = X[valid_rows]
    
    logger.info(f"Running inference on {X_valid.shape[0]:,} pixels...")
    
    # 5. Run inference in chunks
    CHUNK_SIZE = 500_000
    predictions = np.zeros(X_valid.shape[0], dtype=np.float32)
    
    n_chunks = (X_valid.shape[0] + CHUNK_SIZE - 1) // CHUNK_SIZE
    for i in range(n_chunks):
        start = i * CHUNK_SIZE
        end = min((i + 1) * CHUNK_SIZE, X_valid.shape[0])
        predictions[start:end] = model.predict(X_valid[start:end])
        
        if (i + 1) % 10 == 0 or i == n_chunks - 1:
            logger.info(f"  Chunk {i+1}/{n_chunks} done ({end:,} pixels)")
    
    # 6. Reconstruct the output raster - creating a new one cus the predicitons is only valid pixels size and not all
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
    
    logger.info("Phase 3A Prediction Complete!")

if __name__ == "__main__":
    main()
