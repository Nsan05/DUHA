
import pandas as pd
import numpy as np
import rasterio
import matplotlib.pyplot as plt
from matplotlib.colors import TwoSlopeNorm
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

def main():
    """
    Phase 2D.1: Visual Comparison
    
    Side-by-side plot of:
    - Left: VIIRS LST anomaly at 750m (actual observations)
    - Right: Downscaled LST anomaly at 30m (our prediction)
    """
    
    # 1. Load training data and compute anomalies
    logger.info("Loading training CSV...")
    df = pd.read_csv(CSV_PATH)
    scene_means = df.groupby('scene_id')['viirs_lst'].transform('mean')
    df['lst_anomaly'] = df['viirs_lst'] - scene_means
    
    # Pick the scene with the most pixels (best coverage)
    best_scene = df['scene_id'].value_counts().index[0]
    scene_df = df[df['scene_id'] == best_scene].copy()
    logger.info(f"Selected scene: {best_scene} ({len(scene_df)} pixels)")
    
    # 2. Load downscaled 30m raster
    logger.info("Loading downscaled 30m anomaly raster...")
    with rasterio.open(DOWNSCALED_PATH) as src:
        ds_data = src.read(1)
        ds_transform = src.transform
        ds_bounds = src.bounds
    
    # 3. Determine shared spatial extent (crop to VIIRS coverage area)
    viirs_xmin = scene_df['pixel_x'].min() - VIIRS_RES
    viirs_xmax = scene_df['pixel_x'].max() + VIIRS_RES
    viirs_ymin = scene_df['pixel_y'].min() - VIIRS_RES
    viirs_ymax = scene_df['pixel_y'].max() + VIIRS_RES
    
    # Shared colour scale
    vmin = -10
    vmax = 5
    norm = TwoSlopeNorm(vmin=vmin, vcenter=0, vmax=vmax)
    cmap = 'RdYlBu_r'
    
    # 4. Create figure
    fig, axes = plt.subplots(1, 2, figsize=(20, 10))
    
    # -- Panel 1: VIIRS 750m Anomaly (scatter of pixels) --
    ax1 = axes[0]
    half = VIIRS_RES / 2
    
    for _, row in scene_df.iterrows():
        x, y, val = row['pixel_x'], row['pixel_y'], row['lst_anomaly']
        rect = plt.Rectangle(
            (x - half, y - half), VIIRS_RES, VIIRS_RES,
            facecolor=plt.cm.RdYlBu_r(norm(val)),
            edgecolor='none'
        )
        ax1.add_patch(rect)
    
    ax1.set_xlim(viirs_xmin, viirs_xmax)
    ax1.set_ylim(viirs_ymin, viirs_ymax)
    ax1.set_aspect('equal')
    ax1.set_title('VIIRS Observed Anomaly (750m)', fontsize=14, fontweight='bold')
    ax1.set_xlabel('UTM X (m)')
    ax1.set_ylabel('UTM Y (m)')
    
    # -- Panel 2: Downscaled 30m Anomaly --
    ax2 = axes[1]
    
    # Crop the 30m raster to the VIIRS extent
    col_start = max(0, int((viirs_xmin - ds_bounds.left) / 30))
    col_end = min(ds_data.shape[1], int((viirs_xmax - ds_bounds.left) / 30))
    row_start = max(0, int((ds_bounds.top - viirs_ymax) / 30))
    row_end = min(ds_data.shape[0], int((ds_bounds.top - viirs_ymin) / 30))
    
    cropped = ds_data[row_start:row_end, col_start:col_end]
    crop_extent = [
        ds_bounds.left + col_start * 30,
        ds_bounds.left + col_end * 30,
        ds_bounds.top - row_end * 30,
        ds_bounds.top - row_start * 30
    ]
    
    # Mask NaN for display
    cropped_display = np.where(np.isnan(cropped), np.nan, cropped)
    
    im = ax2.imshow(cropped_display, cmap=cmap, norm=norm,
                     extent=crop_extent, interpolation='nearest')
    ax2.set_xlim(viirs_xmin, viirs_xmax)
    ax2.set_ylim(viirs_ymin, viirs_ymax)
    ax2.set_aspect('equal')
    ax2.set_title('Downscaled Prediction (30m)', fontsize=14, fontweight='bold')
    ax2.set_xlabel('UTM X (m)')
    ax2.set_ylabel('UTM Y (m)')
    
    # Shared colourbar
    cbar = fig.colorbar(
        plt.cm.ScalarMappable(norm=norm, cmap=cmap),
        ax=axes, shrink=0.6, aspect=30, pad=0.02,
        label='LST Anomaly (K)\nRed = Hotter than average | Blue = Cooler'
    )
    
    plt.suptitle('Phase 2D.1: Visual Comparison — VIIRS 750m vs Downscaled 30m',
                 fontsize=16, fontweight='bold', y=0.98)
    plt.tight_layout(rect=[0, 0, 0.92, 0.95])
    
    out_path = OUTPUT_DIR / "visual_comparison.png"
    plt.savefig(out_path, dpi=150, bbox_inches='tight')
    logger.info(f"Saved to: {out_path}")
    
    # Quick stats
    logger.info(f"VIIRS anomaly range: {scene_df['lst_anomaly'].min():.2f} to {scene_df['lst_anomaly'].max():.2f} K")
    logger.info(f"Downscaled range (cropped): {np.nanmin(cropped):.2f} to {np.nanmax(cropped):.2f} K")
    logger.info("Done!")

if __name__ == "__main__":
    main()
