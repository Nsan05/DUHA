import pandas as pd
import numpy as np
import rasterio
from rasterio.transform import rowcol
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
from scipy.stats import pearsonr
from pathlib import Path
import logging
import json

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Paths
TRAINING_CSV = Path("data/final/phase3b_training_table.csv")
PREDICTION_TIF = Path("data/final/phase3b_outputs/lst_anomaly_nighttime_30m.tif")
OUTPUT_DIR = Path("data/model_outputs/phase3b")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Model train config
BLOCK_SIZE = 5000
TEST_RATIO = 0.3
RANDOM_STATE = 42

def load_data():
    logger.info(f"Loading CSV: {TRAINING_CSV.name}")
    df = pd.read_csv(TRAINING_CSV)
    
    # Calculate truth anomaly
    scene_means = df.groupby('scene_id')['nighttime_lst'].transform('mean')
    df['true_anomaly'] = df['nighttime_lst'] - scene_means
    
    logger.info(f"Loaded {len(df):,} total observations for evaluation.")
    return df

def analyze_feature_strata(df):
    """
    Computes and plots RMSE and Bias across different feature strata.
    """
    logger.info("Running feature-specific strata analysis...")
    
    df['error'] = df['predicted_anomaly'] - df['true_anomaly']
    
    # Define bins
    df['coast_bin'] = pd.cut(df['dist_to_coast_mean'], bins=[-1, 2000, 5000, 10000, 20000, 100000], labels=['<2km', '2-5km', '5-10km', '10-20km', '>20km'])
    df['density_bin'] = pd.cut(df['building_density_mean'], bins=[-0.1, 0.1, 0.3, 0.6, 1.1], labels=['Low (<10%)', 'Med (10-30%)', 'High (30-60%)', 'Very High (>60%)'])
    df['sand_bin'] = pd.cut(df['sand_mask_fraction'], bins=[-0.1, 0.1, 0.5, 0.9, 1.1], labels=['<10% Sand', '10-50% Sand', '50-90% Sand', '>90% Sand'])
    
    metrics_path = OUTPUT_DIR / "nighttime_30m_metrics.txt"
    with open(metrics_path, "a") as f:
        # Generate Plots
        fig, axes = plt.subplots(1, 3, figsize=(18, 5))
        
        for i, (col, title) in enumerate([('coast_bin', 'Distance to Coast'), 
                                          ('density_bin', 'Building Density'), 
                                          ('sand_bin', 'Sand Fraction')]):
            
            stats = df.groupby(col, observed=True)['error'].agg(
                rmse=lambda x: np.sqrt(np.mean(x**2)),
                bias='mean',
                count='count'
            ).reset_index()
            
            # Write to metrics log
            f.write(f"\n\n--- {title} ---\n")
            f.write(stats.to_string(index=False) + "\n")
            
            # Plot
            ax1 = axes[i]
            ax2 = ax1.twinx()
            
            x = np.arange(len(stats))
            width = 0.35
            
            ax1.bar(x - width/2, stats['rmse'], width, label='RMSE (K)', color='coral')
            ax2.bar(x + width/2, stats['bias'], width, label='Bias (K)', color='skyblue')
            
            ax1.set_ylabel('RMSE (K)')
            if i == 2:
                ax2.set_ylabel('Mean Bias (K)')
            
            ax1.set_title(title)
            ax1.set_xticks(x)
            ax1.set_xticklabels(stats[col], rotation=45, ha='right')
            
            # add zero line for bias
            ax2.axhline(0, color='black', linewidth=0.8, linestyle='--')
            
            if i == 0:
                lines1, labels1 = ax1.get_legend_handles_labels()
                lines2, labels2 = ax2.get_legend_handles_labels()
                ax1.legend(lines1 + lines2, labels1 + labels2, loc='upper left')

        plt.tight_layout()
        plot_path = OUTPUT_DIR / "nighttime_30m_feature_strata.png"
        plt.savefig(plot_path, dpi=200, bbox_inches='tight')
        logger.info(f"Saved feature strata plot to {plot_path}")

def main():
    """
    Phase 3B: Nighttime Evaluation
    
    This compares the 750m VIIRS ground truth against the aggregated 
    (windowed) 30m predictions. 
    """
    
    if not PREDICTION_TIF.exists() or not TRAINING_CSV.exists():
        logger.error("Missing required input files!")
        return
        
    # 1. Load Ground Truth (Full dataset for consistency check)
    full_df = load_data()
    
    logger.info("Sampling predicted 30m TIF and aggregating to 750m windows...")
    
    # 2. Open prediction TIF
    # Because ground truth is 750m, we must aggregate the 30m predictions
    # exactly the same way we aggregated the 30m features (25x25 windows)
    with rasterio.open(PREDICTION_TIF) as src:
        predicted_data = src.read(1)
        transform = src.transform
        
        # Helper to get the 25x25 slice for each pixel
        def get_window_mean(x, y):
            col, row = ~transform * (x, y)
            start_col = int(col - 12) # Half of 25 = 12
            start_row = int(row - 12)
            
            # bounds check
            if start_col < 0 or start_row < 0 or start_col + 25 >= predicted_data.shape[1] or start_row + 25 >= predicted_data.shape[0]:
                return np.nan
                
            window = predicted_data[start_row:start_row+25, start_col:start_col+25]
            
            # Handle nodata/nan
            valid_pixels = window[~np.isnan(window)]
            if len(valid_pixels) == 0:
                return np.nan
            return np.mean(valid_pixels)
            
        full_df['predicted_anomaly'] = full_df.apply(lambda row: get_window_mean(row['pixel_x'], row['pixel_y']), axis=1)
        
    # Drop any NaNs (pixels outside geometry but somehow in dataset)
    full_df = full_df.dropna(subset=['true_anomaly', 'predicted_anomaly'])
    logger.info(f"Final valid comparison pairs: {len(full_df):,}")
    
    # 3. Calculate Metrics
    y_true = full_df['true_anomaly']
    y_pred = full_df['predicted_anomaly']
    
    rmse = np.sqrt(mean_squared_error(y_true, y_pred))
    mae = mean_absolute_error(y_true, y_pred)
    r2 = r2_score(y_true, y_pred)
    pearson_r, p_val = pearsonr(y_true, y_pred)
    mean_bias = np.mean(y_pred - y_true)
    
    logger.info("=" * 50)
    logger.info("PHASE 3B METRICS (Full Dataset Consistency Check)")
    logger.info("=" * 50)
    logger.info(f"  All Pixels:    {len(full_df):,}")
    logger.info(f"  Mean Bias:     {mean_bias:+.3f} K")
    logger.info(f"  MAE:           {mae:.3f} K")
    logger.info(f"  RMSE:          {rmse:.3f} K")
    logger.info(f"  R²:            {r2:.3f}")
    logger.info(f"  Pearson r:     {pearson_r:.3f} (p={p_val:.2e})")
    logger.info("=" * 50)
    
    # 4. Save results string
    metrics_path = OUTPUT_DIR / "nighttime_30m_metrics.txt"
    with open(metrics_path, "w") as f:
        f.write("PHASE 3B METRICS (Full Dataset Consistency Check)\n")
        f.write(f"All Pixels:    {len(full_df):,}\n")
        f.write(f"Mean Bias:     {mean_bias:+.3f} K\n")
        f.write(f"MAE:           {mae:.3f} K\n")
        f.write(f"RMSE:          {rmse:.3f} K\n")
        f.write(f"R²:            {r2:.3f}\n")
        f.write(f"Pearson r:     {pearson_r:.3f} (p={p_val:.2e})\n")
    logger.info(f"Saved metrics to {metrics_path}")
        
    # 5. Scatter Plot Generation
    logger.info("Generating evaluation scatter plot...")
    
    plt.figure(figsize=(10, 8))
    
    # Since n is only ~11k, standard scatter plot is fine (don't need hexbin)
    plt.scatter(y_true, y_pred, alpha=0.3, s=15, c='indigo', edgecolors='none')
    
    # Add perfect agreement line
    min_val = min(y_true.min(), y_pred.min())
    max_val = max(y_true.max(), y_pred.max())
    plt.plot([min_val, max_val], [min_val, max_val], 'r--', lw=2, label='Perfect Agreement (y=x)')
    
    # Formatting
    plt.title('VIIRS 1:30 AM Slot: Predicted vs Observed LST Anomaly\n' + 
              f'(RMSE={rmse:.2f}K, R²={r2:.2f}, N={len(full_df):,})', fontsize=14)
    plt.xlabel('Observed VIIRS Nighttime LST Anomaly (K)', fontsize=12)
    plt.ylabel('Aggregated 30m Predicted LST Anomaly (K)', fontsize=12)
    plt.grid(True, linestyle=':', alpha=0.6)
    plt.legend(loc='upper left')
    
    plot_path = OUTPUT_DIR / "scatter_nighttime.png"
    plt.savefig(plot_path, dpi=200, bbox_inches='tight')
    logger.info(f"Saved scatter plot to {plot_path}")
    
    # 6. Feature Strata Analysis
    analyze_feature_strata(full_df)

if __name__ == "__main__":
    main()
