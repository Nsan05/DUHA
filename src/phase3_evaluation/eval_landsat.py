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
TRAINING_CSV = Path("data/final/phase3a_training_table.csv")
PREDICTION_TIF = Path("data/final/phase3a_outputs/lst_anomaly_landsat_30m.tif")
OUTPUT_DIR = Path("data/model_outputs/phase3a")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
REF_GRID_META = Path("data/intermediate/grids/reference_grid_meta.json")

# Model train config
BLOCK_SIZE = 5000
TEST_RATIO = 0.3
RANDOM_STATE = 42

def recreate_test_split(df):
    """
    Recreates the exact same spatial block split used during training
    to extract ONLY the Test subset for unbiased evaluation.
    """
    logger.info(f"Recreating {BLOCK_SIZE}m spatial split to extract Test set...")
    
    # Assign Block IDs
    df['block_x'] = (df['pixel_x'] // BLOCK_SIZE).astype(int)
    df['block_y'] = (df['pixel_y'] // BLOCK_SIZE).astype(int)
    
    blocks = df[['block_x', 'block_y']].drop_duplicates()
    
    np.random.seed(RANDOM_STATE)
    shuffled_blocks = blocks.sample(frac=1, random_state=RANDOM_STATE).reset_index(drop=True)
    
    n_test_blocks = int(len(blocks) * TEST_RATIO)
    test_blocks_df = shuffled_blocks.iloc[:n_test_blocks]
    
    test_blocks_set = set(zip(test_blocks_df['block_x'], test_blocks_df['block_y']))
    
    is_test = df.apply(lambda row: (row['block_x'], row['block_y']) in test_blocks_set, axis=1)
    
    test_df = df[is_test].copy()
    logger.info(f"Recovered {len(test_df):,} test pixels.")
    return test_df

def load_data():
    logger.info(f"Loading CSV: {TRAINING_CSV.name}")
    # Load all 24M rows, but only required columns, explicitly typed to save memory
    df = pd.read_csv(TRAINING_CSV, 
                     usecols=['pixel_x', 'pixel_y', 'scene_id', 'landsat_lst',
                              'building_density_mean', 'dist_to_coast_m', 'sand_mask_fraction', 'ndvi_std'],
                     dtype={
                         'pixel_x': np.float32, 
                         'pixel_y': np.float32, 
                         'scene_id': str, 
                         'landsat_lst': np.float32,
                         'building_density_mean': np.float32,
                         'dist_to_coast_m': np.float32,
                         'sand_mask_fraction': np.float32,
                         'ndvi_std': np.float32
                     })
    
    # Calculate truth anomaly
    scene_means = df.groupby('scene_id')['landsat_lst'].transform('mean')
    df['true_anomaly'] = df['landsat_lst'] - scene_means
    
    test_df = recreate_test_split(df)
    return test_df

def analyze_feature_strata(df):
    """
    Computes and plots RMSE and Bias across different feature strata.
    """
    logger.info("Running feature-specific strata analysis...")
    
    df['error'] = df['predicted_anomaly'] - df['true_anomaly']
    
    # Define bins
    df['coast_bin'] = pd.cut(df['dist_to_coast_m'], bins=[-1, 2000, 5000, 10000, 20000, 100000], labels=['<2km', '2-5km', '5-10km', '10-20km', '>20km'])
    df['density_bin'] = pd.cut(df['building_density_mean'], bins=[-0.1, 0.1, 0.3, 0.6, 1.1], labels=['Low (<10%)', 'Med (10-30%)', 'High (30-60%)', 'Very High (>60%)'])
    df['sand_bin'] = pd.cut(df['sand_mask_fraction'], bins=[-0.1, 0.1, 0.5, 0.9, 1.1], labels=['<10% Sand', '10-50% Sand', '50-90% Sand', '>90% Sand'])
    df['ndvi_std_bin'] = pd.cut(df['ndvi_std'], bins=[-0.1, 0.01, 0.05, 0.1, 1.0], labels=['Uniform', 'Low Var.', 'Med Var.', 'High Var.'])
    
    metrics_path = OUTPUT_DIR / "landsat_30m_metrics.txt"
    with open(metrics_path, "a") as f:
        # Generate Plots
        fig, axes = plt.subplots(1, 4, figsize=(24, 5))
        
        for i, (col, title) in enumerate([('coast_bin', 'Distance to Coast'), 
                                          ('density_bin', 'Building Density'), 
                                          ('sand_bin', 'Sand Fraction'),
                                          ('ndvi_std_bin', 'NDVI Variance')]):
            
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
            if i == 3:
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
        plot_path = OUTPUT_DIR / "landsat_30m_feature_strata.png"
        plt.savefig(plot_path, dpi=200, bbox_inches='tight')
        logger.info(f"Saved feature strata plot to {plot_path}")

def main():
    """
    Phase 3A: Landsat Evaluation
    
    Direct pixel-to-pixel comparison since both ground truth and prediction
    are at native 30m resolution.
    """
    
    if not PREDICTION_TIF.exists() or not TRAINING_CSV.exists():
        logger.error("Missing required input files!")
        return
        
    # 1. Load Ground Truth (Test set only)
    test_df = load_data()
    
    logger.info("Sampling predicted 30m TIF at test locations...")
    
    # 2. Open prediction TIF and get transform
    with rasterio.open(PREDICTION_TIF) as src:
        predicted_data = src.read(1)
        transform = src.transform
        
        # Convert all test coordinates into row/col indices
        # rowcol handles arrays natively
        rows, cols = rowcol(transform, test_df['pixel_x'], test_df['pixel_y'])
        
        # Sample the 2D array
        test_df['predicted_anomaly'] = predicted_data[rows, cols]
        
    # Drop any NaNs (pixels outside geometry but somehow in test set)
    test_df = test_df.dropna(subset=['true_anomaly', 'predicted_anomaly'])
    logger.info(f"Final valid comparison pairs: {len(test_df):,}")
    
    # 3. Calculate Metrics
    y_true = test_df['true_anomaly']
    y_pred = test_df['predicted_anomaly']
    
    rmse = np.sqrt(mean_squared_error(y_true, y_pred))
    mae = mean_absolute_error(y_true, y_pred)
    r2 = r2_score(y_true, y_pred)
    pearson_r, p_val = pearsonr(y_true, y_pred)
    mean_bias = np.mean(y_pred - y_true)
    
    logger.info("=" * 50)
    logger.info("PHASE 3A DIRECT PIXEL-TO-PIXEL METRICS (30m native)")
    logger.info("=" * 50)
    logger.info(f"  Test Pixels:   {len(test_df):,}")
    logger.info(f"  Mean Bias:     {mean_bias:+.3f} K")
    logger.info(f"  MAE:           {mae:.3f} K")
    logger.info(f"  RMSE:          {rmse:.3f} K")
    logger.info(f"  R²:            {r2:.3f}")
    logger.info(f"  Pearson r:     {pearson_r:.3f} (p={p_val:.2e})")
    logger.info("=" * 50)
    
    # 4. Save results string
    metrics_path = OUTPUT_DIR / "landsat_30m_metrics.txt"
    with open(metrics_path, "w") as f:
        f.write("PHASE 3A DIRECT PIXEL-TO-PIXEL METRICS (30m native)\n")
        f.write(f"Test Pixels:   {len(test_df):,}\n")
        f.write(f"Mean Bias:     {mean_bias:+.3f} K\n")
        f.write(f"MAE:           {mae:.3f} K\n")
        f.write(f"RMSE:          {rmse:.3f} K\n")
        f.write(f"R²:            {r2:.3f}\n")
        f.write(f"Pearson r:     {pearson_r:.3f} (p={p_val:.2e})\n")
    logger.info(f"Saved metrics to {metrics_path}")
        
    # 5. Scatter Plot Generation
    logger.info("Generating evaluation scatter plot...")
    
    # For a massive 7-million point scatter plot, hexbin is much faster and clearer
    plt.figure(figsize=(10, 8))
    
    hb = plt.hexbin(
        y_true, y_pred, 
        gridsize=150, 
        cmap='inferno', 
        mincnt=1,
        bins='log' # Log scale colors for density
    )
    
    cb = plt.colorbar(hb, label='log10(Density of Pixels)')
    
    # Add perfect agreement line
    min_val = min(y_true.min(), y_pred.min())
    max_val = max(y_true.max(), y_pred.max())
    plt.plot([min_val, max_val], [min_val, max_val], 'r--', lw=2, label='Perfect Agreement (y=x)')
    
    # Formatting
    plt.title('Landsat 10:30 AM Slot: Predicted vs Observed 30m LST Anomaly\n' + 
              f'(RMSE={rmse:.2f}K, R²={r2:.2f}, N={len(test_df):,})', fontsize=14)
    plt.xlabel('Observed Landsat LST Anomaly (K)', fontsize=12)
    plt.ylabel('Predicted LST Anomaly (K)', fontsize=12)
    plt.grid(True, linestyle=':', alpha=0.6)
    plt.legend(loc='upper left')
    
    plot_path = OUTPUT_DIR / "scatter_landsat_30m.png"
    plt.savefig(plot_path, dpi=200, bbox_inches='tight')
    logger.info(f"Saved scatter plot to {plot_path}")
    
    # 6. Feature Strata Analysis
    analyze_feature_strata(test_df)

if __name__ == "__main__":
    main()