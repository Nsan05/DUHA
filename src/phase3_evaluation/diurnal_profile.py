import numpy as np
import rasterio
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
import logging

# Setup Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Paths
INPUT_TIFS = {
    'Morning (10:30 AM)': Path("data/final/phase3a_outputs/lst_anomaly_landsat_30m.tif"),
    'Afternoon (1:30 PM)': Path("data/final/phase2_outputs/lst_anomaly_30m.tif"),
    'Night (1:30 AM)': Path("data/final/phase3b_outputs/lst_anomaly_nighttime_30m.tif")
}

OUTPUT_DIR = Path("data/final/phase3c_outputs")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

OUT_3PANEL = OUTPUT_DIR / "diurnal_3panel.png"
OUT_RANGE_TIF = OUTPUT_DIR / "diurnal_range_30m.tif"
OUT_STATS_CSV = OUTPUT_DIR / "diurnal_summary_stats.csv"

def main():
    logger.info("PHASE 3C: DIURNAL FUSION STARTED")
    logger.info("-" * 40)
    
    # 1. Load and align the three anomaly TIFs
    data_arrays = {}
    meta = None
    
    for name, path in INPUT_TIFS.items():
        if not path.exists():
            logger.error(f"Missing input TIF: {path}")
            return
            
        logger.info(f"Loading {name} from {path.name}...")
        with rasterio.open(path) as src:
            data = src.read(1)
            # Ensuring nan for nodata 
            if src.nodata is not None:
                data[data == src.nodata] = np.nan
            data_arrays[name] = data
            
            if meta is None:
                meta = src.meta.copy()
    
    # Create shared valid mask (pixels non-NaN in all three)
    logger.info("Creating shared validity mask...")
    shared_mask = np.ones(data_arrays['Morning (10:30 AM)'].shape, dtype=bool)
    for name, data in data_arrays.items():
        shared_mask &= ~np.isnan(data)
        
    n_valid = np.sum(shared_mask)
    n_total = shared_mask.size
    logger.info(f"Shared valid urban pixels: {n_valid:,} ({n_valid/n_total:.1%})")
    
    # Apply shared mask so that out-of-bounds become exactly NaN everywhere
    for name in data_arrays.keys():
        data_arrays[name][~shared_mask] = np.nan

    # 2. Generate the 3-panel comparison map
    logger.info("Generating 3-panel comparison map...")
    
    # Find global min/max for 95th/5th percentiles to have a shared, robust color scale
    all_valid_pixels = np.concatenate([data_arrays[name][shared_mask] for name in data_arrays.keys()])
    vmax = np.percentile(all_valid_pixels, 98)
    vmin = -vmax  # symmetric color scale around 0 is usually best for anomalies
    
    fig, axes = plt.subplots(1, 3, figsize=(24, 8))
    
    for ax, (name, data) in zip(axes, data_arrays.items()):
        im = ax.imshow(data, cmap='RdBu_r', vmin=vmin, vmax=vmax, interpolation='none')
        ax.set_title(f"{name} LST Anomaly", fontsize=16, pad=10)
        ax.axis('off')
        
    # Shared colorbar
    cbar = fig.colorbar(im, ax=axes.ravel().tolist(), orientation='vertical', fraction=0.015, pad=0.02)
    cbar.set_label('LST Anomaly (K)', fontsize=14)
    cbar.ax.tick_params(labelsize=12)
    
    plt.suptitle('Diurnal Urban Heat Anomalies Across 30m Downscaled Models', fontsize=20, y=0.95)
    
    plt.savefig(OUT_3PANEL, dpi=300, bbox_inches='tight', facecolor='white')
    logger.info(f"Saved 3-panel map to {OUT_3PANEL}")
    plt.close()
    
    # 3. Compute and save the Diurnal Range TIF
    logger.info("Computing Diurnal Range (Afternoon - Night)...")
    diurnal_range = data_arrays['Afternoon (1:30 PM)'] - data_arrays['Night (1:30 AM)']
    # Ensure background is NaN
    diurnal_range[~shared_mask] = np.nan
    
    logger.info(f"Saving Diurnal Range GeoTIFF to {OUT_RANGE_TIF}")
    meta.update({'nodata': np.nan, 'dtype': 'float32'})
    with rasterio.open(OUT_RANGE_TIF, 'w', **meta) as dst:
        dst.write(diurnal_range.astype(np.float32), 1)
        
    # 4. Generate CSV summary statistics
    logger.info("Computing summary statistics...")
    
    stats_data = {}
    
    def compute_stats(arr_1d, label):
        return {
            'Slot': label,
            'Mean (K)': np.mean(arr_1d),
            'Median (K)': np.median(arr_1d),
            'Std Dev (K)': np.std(arr_1d),
            'Min (K)': np.min(arr_1d),
            'Max (K)': np.max(arr_1d),
            '5th Percentile (K)': np.percentile(arr_1d, 5),
            '95th Percentile (K)': np.percentile(arr_1d, 95)
        }

    records = []
    
    for name, data in data_arrays.items():
        valid_pixels = data[shared_mask]
        records.append(compute_stats(valid_pixels, name))
        
    # Add diurnal range stats
    records.append(compute_stats(diurnal_range[shared_mask], "Diurnal Range (Afternoon - Night)"))
    
    df_stats = pd.DataFrame(records)
    df_stats.to_csv(OUT_STATS_CSV, index=False)
    
    logger.info(f"Saved summary stats to {OUT_STATS_CSV}")
    
    logger.info("-" * 40)
    logger.info("Summary Statistics Preview:")
    for _, row in df_stats.iterrows():
        logger.info(f"  [{row['Slot']}]  Mean: {row['Mean (K)']:+.2f}K | Range: {row['Min (K)']:.2f}K to {row['Max (K)']:.2f}K")
    logger.info("-" * 40)
    
    logger.info("Phase 3C Script Complete!")

if __name__ == "__main__":
    main()
