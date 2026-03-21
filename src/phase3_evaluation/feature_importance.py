import pandas as pd
import numpy as np
import joblib
import logging
import matplotlib.pyplot as plt
from pathlib import Path
from sklearn.inspection import permutation_importance

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def clean_label(label):
    return label.replace('_mean', '').replace('_fraction', '').replace('_m', '').replace('_', ' ').title()

def get_landsat_data():
    csv_path = Path("data/final/phase3a_training_table.csv")
    logger.info(f"Loading {csv_path.name}...")
    
    # Selecting the exact columns used by the model
    features = [
        'ndvi_mean', 'ndvi_std', 
        'albedo_mean', 'albedo_std', 
        'building_density_mean', 'building_density_std', 
        'height_mean', 'height_std',
        'road_density_mean', 'road_density_std', 
        'sand_mask_fraction', 'water_mask_full_fraction', 
        'dist_to_coast_m'
    ]
    
    # Load efficiently - forces data to be float32 to save memory
    dtypes = {f: np.float32 for f in features}
    dtypes['landsat_lst'] = np.float32
    dtypes['scene_id'] = str
    
    df = pd.read_csv(csv_path, usecols=['scene_id', 'landsat_lst'] + features, dtype=dtypes)
    
    # Recreate the target anomaly
    logger.info(f"Computing anomaly for Morning...")
    scene_means = df.groupby('scene_id')['landsat_lst'].transform('mean')
    df['lst_anomaly_landsat'] = df['landsat_lst'] - scene_means
    
    # The landsat dataset is 24M rows, permutation importance will take hours if we use all of it.
    # We will sample 50,000 random pixels, which is more than enough to perfectly estimate feature importance.
    df_sample = df.sample(n=50000, random_state=42)
    
    return df_sample[features], df_sample['lst_anomaly_landsat'], features

def get_night_data():
    csv_path = Path("data/final/phase3b_training_table.csv")
    logger.info(f"Loading {csv_path.name}...")
    
    features = [
        'ndvi_mean', 'ndvi_std', 
        'albedo_mean', 'albedo_std', 
        'building_density_mean', 'building_density_std', 
        'height_mean', 'height_std',
        'road_density_mean', 'road_density_std', 
        'sand_mask_fraction', 'water_mask_full_fraction', 
        'dist_to_coast_mean'
    ]
    
    df = pd.read_csv(csv_path)
    
    logger.info(f"Computing anomaly for Nighttime...")
    scene_means = df.groupby('scene_id')['nighttime_lst'].transform('mean')
    df['lst_anomaly_nighttime'] = df['nighttime_lst'] - scene_means
    
    df = df.dropna(subset=['lst_anomaly_nighttime'] + features)
    
    # Cap at 50,000 for consistency, though this dataset only has ~38k
    n_sample = min(50000, len(df))
    df_sample = df.sample(n=n_sample, random_state=42)
    
    return df_sample[features], df_sample['lst_anomaly_nighttime'], features

def plot_importance(result, features, ax, title):
    # Sort features by importance
    sorted_idx = result.importances_mean.argsort()
    # Orders features from least → most important
    labels = np.array(features)[sorted_idx]
    
    # Clean up labels for display
    clean_labels = [clean_label(l) for l in labels]
    
    ax.boxplot(
        result.importances[sorted_idx].T,
        vert=False,
        labels=clean_labels,
        patch_artist=True,
        boxprops=dict(facecolor="skyblue", color="black"),
        medianprops=dict(color="red"),
    )
    ax.set_title(title, fontsize=14, pad=10)
    ax.set_xlabel("Permutation Importance (R² drop when shuffled)", fontsize=12)
    ax.grid(axis='x', linestyle='--', alpha=0.7)

def main():
    logger.info("PHASE 3: FEATURE IMPORTANCE ANALYSIS")
    logger.info("-" * 40)
    
    OUTPUT_DIR = Path("data/final/phase3c_outputs")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    # -----------------------------------------------------
    # 1. Landsat (Morning)
    # -----------------------------------------------------
    model_l_path = Path("data/models/gb_model_landsat.joblib")
    if not model_l_path.exists():
        logger.error(f"Missing model: {model_l_path}")
        return
        
    X_l, y_l, feats_l = get_landsat_data()
    logger.info("Loading Landsat model...")
    model_l = joblib.load(model_l_path)
    
    logger.info("Computing Landsat permutation importance (this checks 5 shuffles per feature)...")
    res_l = permutation_importance(model_l, X_l, y_l, n_repeats=5, random_state=42, n_jobs=-1, scoring='r2')
    
    # -----------------------------------------------------
    # 2. VIIRS (Nighttime)
    # -----------------------------------------------------
    model_n_path = Path("data/models/gb_model_nighttime.joblib")
    if not model_n_path.exists():
        logger.error(f"Missing model: {model_n_path}")
        return
        
    X_n, y_n, feats_n = get_night_data()
    logger.info("Loading Nighttime model...")
    model_n = joblib.load(model_n_path)
    
    logger.info("Computing Nighttime permutation importance...")
    res_n = permutation_importance(model_n, X_n, y_n, n_repeats=5, random_state=42, n_jobs=-1, scoring='r2')
    
    # -----------------------------------------------------
    # 3. Plot Comparison
    # -----------------------------------------------------
    logger.info("Generating side-by-side boxplots...")
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(18, 7))
    
    plot_importance(res_l, feats_l, ax1, "Landsat Morning (10:30 AM) Features")
    plot_importance(res_n, feats_n, ax2, "VIIRS Nighttime (1:30 AM) Features")
    
    plt.tight_layout()
    out_path = OUTPUT_DIR / "feature_importance_comparison.png"
    plt.savefig(out_path, dpi=300, bbox_inches='tight', facecolor='white')
    logger.info(f"Saved feature importance chart to: {out_path}")
    logger.info("-" * 40)
    logger.info("Feature Importance Analysis Complete!")

if __name__ == "__main__":
    main()
