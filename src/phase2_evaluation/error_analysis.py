import pandas as pd
import numpy as np
import rasterio
from rasterio.transform import rowcol
import matplotlib.pyplot as plt
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

VIIRS_RES = 750
HALF_RES = VIIRS_RES / 2

def compute_metrics(actual, predicted):
    """Compute error metrics for a group of pixels."""
    error = predicted - actual
    return {
        'N': len(actual),
        'Bias': np.mean(error),
        'MAE': np.mean(np.abs(error)),
        'RMSE': np.sqrt(mean_squared_error(actual, predicted)),
        'R²': r2_score(actual, predicted) if len(actual) > 1 else np.nan
    }

def main():
    """
    Phase 2D.3: Error Analysis by Land Cover
    
    Splits 750m pixels into categories and compares model errors:
    1. Sandy vs Non-Sandy
    2. High-Density vs Low-Density
    3. Near-Coast vs Inland
    """
    
    # 1. Load training data and compute anomalies
    logger.info("Loading training CSV...")
    df = pd.read_csv(CSV_PATH)
    scene_means = df.groupby('scene_id')['viirs_lst'].transform('mean')
    df['lst_anomaly'] = df['viirs_lst'] - scene_means
    
    # 2. Load downscaled 30m raster and aggregate to 750m (same as 2D.2)
    logger.info("Loading downscaled 30m raster and aggregating to 750m...")
    with rasterio.open(DOWNSCALED_PATH) as src:
        ds_data = src.read(1)
        ds_transform = src.transform
        ds_shape = ds_data.shape
    
    # Aggregate 30m predictions to 750m for each unique pixel
    unique_pixels = df[['pixel_x', 'pixel_y']].drop_duplicates()
    agg_predictions = {}
    
    for _, row in unique_pixels.iterrows():
        px, py = row['pixel_x'], row['pixel_y']
        x_min, x_max = px - HALF_RES, px + HALF_RES
        y_min, y_max = py - HALF_RES, py + HALF_RES
        
        row_top, col_left = rowcol(ds_transform, x_min, y_max)
        row_bot, col_right = rowcol(ds_transform, x_max, y_min)
        
        r_min = max(0, min(row_top, row_bot))
        r_max = min(ds_shape[0], max(row_top, row_bot))
        c_min = max(0, min(col_left, col_right))
        c_max = min(ds_shape[1], max(col_left, col_right))
        
        if r_min >= r_max or c_min >= c_max:
            continue
        
        block = ds_data[r_min:r_max, c_min:c_max]
        valid = block[~np.isnan(block)]
        if valid.size > 0:
            agg_predictions[(px, py)] = np.mean(valid)
    
    df['pred_agg'] = df.apply(
        lambda r: agg_predictions.get((r['pixel_x'], r['pixel_y']), np.nan), axis=1
    )
    df = df.dropna(subset=['pred_agg']).copy()
    logger.info(f"Matched {len(df)} observations for error analysis")
    
    # 3. Define categories
    median_density = df['building_density_mean'].median()
    
    categories = {
        # Sandy vs Non-Sandy
        'Sandy (>50%)': df['sand_mask_fraction'] > 0.5,
        'Non-Sandy (≤50%)': df['sand_mask_fraction'] <= 0.5,
        # High vs Low Building Density
        f'High Density (>{median_density:.3f})': df['building_density_mean'] > median_density,
        f'Low Density (≤{median_density:.3f})': df['building_density_mean'] <= median_density,
        # Near-Coast vs Inland
        'Near Coast (<5km)': df['dist_to_coast_m'] < 5000,
        'Inland (≥5km)': df['dist_to_coast_m'] >= 5000,
    }
    
    # 4. Compute metrics for each category
    logger.info("\n" + "=" * 70)
    logger.info("ERROR ANALYSIS BY LAND COVER")
    logger.info("=" * 70)
    
    results = []
    for name, mask in categories.items():
        subset = df[mask]
        if len(subset) < 10:
            continue
        metrics = compute_metrics(subset['lst_anomaly'].values, subset['pred_agg'].values)
        metrics['Category'] = name
        results.append(metrics)
        logger.info(f"  {name:30s} | N={metrics['N']:6,} | Bias={metrics['Bias']:+.2f}K | "
                     f"MAE={metrics['MAE']:.2f}K | RMSE={metrics['RMSE']:.2f}K | R²={metrics['R²']:.3f}")
    
    logger.info("=" * 70)
    
    # 5. Create grouped bar chart
    fig, axes = plt.subplots(1, 3, figsize=(18, 6))
    
    comparison_groups = [
        ('Sandy vs Non-Sandy', ['Sandy (>50%)', 'Non-Sandy (≤50%)']),
        ('Building Density', [r['Category'] for r in results if 'Density' in r['Category']]),
        ('Distance to Coast', ['Near Coast (<5km)', 'Inland (≥5km)']),
    ]
    
    colors = ['#e74c3c', '#3498db']  # Red, Blue
    
    for ax, (title, cat_names) in zip(axes, comparison_groups):
        group = [r for r in results if r['Category'] in cat_names]
        if len(group) < 2:
            continue
        
        x = np.arange(3)  # Bias, MAE, RMSE
        width = 0.35
        
        for i, (cat, color) in enumerate(zip(group, colors)):
            values = [cat['Bias'], cat['MAE'], cat['RMSE']]
            bars = ax.bar(x + i * width - width/2, values, width, 
                         label=cat['Category'], color=color, alpha=0.8, edgecolor='white')
            
            # Value labels on bars
            for bar, val in zip(bars, values):
                ax.text(bar.get_x() + bar.get_width()/2, bar.get_y() + bar.get_height() + 0.05,
                       f'{val:.2f}', ha='center', va='bottom', fontsize=9, fontweight='bold')
        
        ax.set_xticks(x)
        ax.set_xticklabels(['Bias (K)', 'MAE (K)', 'RMSE (K)'], fontsize=11)
        ax.set_title(title, fontsize=13, fontweight='bold')
        ax.legend(fontsize=8, loc='upper right')
        ax.axhline(y=0, color='gray', linestyle='--', linewidth=0.5)
        ax.set_ylabel('Value (K)')
    
    plt.suptitle('Phase 2D.3: Error Analysis by Land Cover Category',
                 fontsize=15, fontweight='bold', y=1.02)
    plt.tight_layout()
    
    out_path = OUTPUT_DIR / "error_analysis_landcover.png"
    plt.savefig(out_path, dpi=150, bbox_inches='tight')
    logger.info(f"\nBar chart saved to: {out_path}")
    
    # 6. Also create a summary table as CSV
    results_df = pd.DataFrame(results)
    results_df = results_df[['Category', 'N', 'Bias', 'MAE', 'RMSE', 'R²']]
    table_path = OUTPUT_DIR / "error_analysis_summary.csv"
    results_df.to_csv(table_path, index=False, float_format='%.3f')
    logger.info(f"Summary table saved to: {table_path}")
    logger.info("Done!")

if __name__ == "__main__":
    main()
