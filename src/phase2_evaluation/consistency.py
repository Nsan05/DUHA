import pandas as pd
import numpy as np
import rasterio
from rasterio.transform import rowcol
import matplotlib.pyplot as plt
from scipy import stats
from sklearn.metrics import mean_squared_error, r2_score
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Paths
CSV_PATH = Path("data/final/phase2_training_table_enriched.csv")
DOWNSCALED_PATH = Path("data/final/phase2_outputs/lst_anomaly_30m.tif")
OUTPUT_DIR = Path("data/model_outputs/phase2d")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

VIIRS_RES = 750  # meters
HALF_RES = VIIRS_RES / 2

def main():
    """
    Phase 2D.2: Statistical Consistency
    
    For each 750m VIIRS pixel in the training CSV:
    1. Find the 25x25 block of 30m pixels that fall within it.
    2. Average those 30m predictions -> aggregated 750m prediction.
    3. Compare to the actual VIIRS anomaly.
    """
    
    # 1. Load training data and compute anomalies
    logger.info("Loading training CSV...")
    df = pd.read_csv(CSV_PATH)
    scene_means = df.groupby('scene_id')['viirs_lst'].transform('mean')
    df['lst_anomaly'] = df['viirs_lst'] - scene_means
    logger.info(f"Loaded {len(df)} pixel-observations across {df['scene_id'].nunique()} scenes")
    
    # 2. Load downscaled 30m raster
    logger.info("Loading downscaled 30m anomaly raster...")
    with rasterio.open(DOWNSCALED_PATH) as src:
        ds_data = src.read(1)
        ds_transform = src.transform
        ds_shape = ds_data.shape
    
    # 3. For each 750m pixel, aggregate the 30m predictions
    logger.info("Aggregating 30m predictions back to 750m...")
    
    # Get unique pixel locations (same pixel appears in multiple scenes but maps to same 30m block)
    unique_pixels = df[['pixel_x', 'pixel_y']].drop_duplicates()
    logger.info(f"Unique 750m pixel locations: {len(unique_pixels)}")
    
    # Pre-compute the aggregated 30m prediction for each unique pixel location
    agg_predictions = {}
    
    for _, row in unique_pixels.iterrows():
        px, py = row['pixel_x'], row['pixel_y']
        
        # 750m pixel bounds
        x_min = px - HALF_RES
        x_max = px + HALF_RES
        y_min = py - HALF_RES
        y_max = py + HALF_RES
        
        # Convert to 30m raster row/col indices
        row_top, col_left = rowcol(ds_transform, x_min, y_max)
        row_bot, col_right = rowcol(ds_transform, x_max, y_min)
        
        # Ensure correct ordering
        r_min = max(0, min(row_top, row_bot))
        r_max = min(ds_shape[0], max(row_top, row_bot))
        c_min = max(0, min(col_left, col_right))
        c_max = min(ds_shape[1], max(col_left, col_right))
        
        if r_min >= r_max or c_min >= c_max:
            continue
        
        # Extract the 25x25 block of 30m pixels
        block = ds_data[r_min:r_max, c_min:c_max]
        valid = block[~np.isnan(block)]
        
        if valid.size > 0:
            agg_predictions[(px, py)] = np.mean(valid)
    
    logger.info(f"Successfully aggregated {len(agg_predictions)} pixel locations")
    
    # 4. Match with actual VIIRS anomalies -  add column for agg
    df['pred_agg'] = df.apply(
        lambda r: agg_predictions.get((r['pixel_x'], r['pixel_y']), np.nan), axis=1
    )
    
    # Drop rows without predictions
    valid_df = df.dropna(subset=['pred_agg']).copy()
    logger.info(f"Matched observations: {len(valid_df)} (from {len(df)} total)")
    
    actual = valid_df['lst_anomaly'].values
    predicted = valid_df['pred_agg'].values
    
    # 5. Compute metrics
    bias = np.mean(predicted - actual)
    rmse = np.sqrt(mean_squared_error(actual, predicted))
    r2 = r2_score(actual, predicted)
    # When VIIRS anomaly increases, does the prediction also increase?
    pearson_r, p_val = stats.pearsonr(actual, predicted)
    mae = np.mean(np.abs(predicted - actual))
    
    logger.info("=" * 50)
    logger.info("STATISTICAL CONSISTENCY METRICS")
    logger.info("=" * 50)
    logger.info(f"  Observations:       {len(valid_df)}")
    logger.info(f"  Mean Bias:          {bias:+.3f} K")
    logger.info(f"  MAE:                {mae:.3f} K")
    logger.info(f"  RMSE:               {rmse:.3f} K")
    logger.info(f"  R²:                 {r2:.3f}")
    logger.info(f"  Pearson r:          {pearson_r:.3f} (p={p_val:.2e})")
    logger.info("=" * 50)
    logger.info(f"  Training R²:        0.48  (for comparison)")
    logger.info(f"  Training RMSE:      2.10 K (for comparison)")
    logger.info("=" * 50)
    
    # 6. Scatter plot: Aggregated Prediction vs Actual VIIRS
    fig, ax = plt.subplots(figsize=(8, 8))
    
    ax.scatter(actual, predicted, alpha=0.15, s=8, c='steelblue', edgecolors='none')
    
    # 1:1 reference line
    lims = [min(actual.min(), predicted.min()) - 1, max(actual.max(), predicted.max()) + 1]
    ax.plot(lims, lims, 'k--', linewidth=1, label='1:1 Line')
    
    # Best fit line
    slope, intercept = np.polyfit(actual, predicted, 1)
    x_fit = np.linspace(lims[0], lims[1], 100)
    ax.plot(x_fit, slope * x_fit + intercept, 'r-', linewidth=1.5,
            label=f'Best Fit (slope={slope:.2f})')
    
    ax.set_xlim(lims)
    ax.set_ylim(lims)
    ax.set_aspect('equal')
    ax.set_xlabel('Actual VIIRS Anomaly (K)', fontsize=12)
    ax.set_ylabel('Aggregated 30m Prediction (K)', fontsize=12)
    ax.set_title('Phase 2D.2: Statistical Consistency\n30m→750m Aggregation vs VIIRS', fontsize=14)
    ax.legend(fontsize=10)
    
    # Metrics text box
    textstr = (f'N = {len(valid_df):,}\n'
               f'Bias = {bias:+.2f} K\n'
               f'RMSE = {rmse:.2f} K\n'
               f'R² = {r2:.3f}\n'
               f'r = {pearson_r:.3f}')
    ax.text(0.05, 0.95, textstr, transform=ax.transAxes, fontsize=11,
            verticalalignment='top', bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))
    
    plt.tight_layout()
    out_path = OUTPUT_DIR / "statistical_consistency.png"
    plt.savefig(out_path, dpi=150, bbox_inches='tight')
    logger.info(f"Scatter plot saved to: {out_path}")
    logger.info("Done!")

if __name__ == "__main__":
    main()
