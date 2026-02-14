
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import joblib
from pathlib import Path
from sklearn.inspection import permutation_importance, PartialDependenceDisplay
from sklearn.metrics import mean_squared_error, r2_score

# Setup Logging
import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Paths
DATA_DIR = Path("data/final")
INPUT_FILE = DATA_DIR / "phase2_training_table_enriched.csv"
MODELS_DIR = Path("data/models")
OUTPUT_DIR = Path("data/model_outputs/interpretation")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Configuration 
BLOCK_SIZE = 5000
TEST_RATIO = 0.3
RANDOM_STATE = 42

FEATURES = [
    'ndvi_mean',
    'albedo_mean',
    'building_density_mean',
    'height_mean',
    'road_density_mean',
    'sand_mask_fraction',
    'water_mask_full_fraction',
    'dist_to_coast_m'
]

# Human-readable labels for plots
FEATURE_LABELS = {
    'ndvi_mean': 'Vegetation (NDVI)',
    'albedo_mean': 'Surface Reflectivity (Albedo)',
    'building_density_mean': 'Building Density',
    'height_mean': 'Building Height (m)',
    'road_density_mean': 'Road Density',
    'sand_mask_fraction': 'Sand/Bare Soil Fraction',
    'water_mask_full_fraction': 'Water Fraction',
    'dist_to_coast_m': 'Distance to Coast (m)'
}

TARGET_RAW = 'viirs_lst'
TARGET_ANOMALY = 'lst_anomaly'

def load_and_prep_data():
    """Loads data and recreates the Training/Test split exactly as Phase 2B."""
    logger.info("Loading Data...")
    df = pd.read_csv(INPUT_FILE)
    
    # Recalculate Anomaly
    logger.info("Recalculating LST Anomalies...")
    scene_means = df.groupby('scene_id')[TARGET_RAW].transform('mean')
    df[TARGET_ANOMALY] = df[TARGET_RAW] - scene_means
    
    # Recreate Spatial Split
    logger.info(f"Recreating Spatial Split ({BLOCK_SIZE}m blocks)...")
    df['block_x'] = (df['pixel_x'] // BLOCK_SIZE).astype(int)
    df['block_y'] = (df['pixel_y'] // BLOCK_SIZE).astype(int)
    
    blocks = df[['block_x', 'block_y']].drop_duplicates()
    shuffled_blocks = blocks.sample(frac=1, random_state=RANDOM_STATE).reset_index(drop=True)
    
    n_test_blocks = int(len(blocks) * TEST_RATIO)
    test_blocks_df = shuffled_blocks.iloc[:n_test_blocks]
    test_blocks_set = set(zip(test_blocks_df['block_x'], test_blocks_df['block_y']))
    
    df['is_test'] = df.apply(lambda row: (row['block_x'], row['block_y']) in test_blocks_set, axis=1)
    
    train_df = df[~df['is_test']].copy()
    test_df = df[df['is_test']].copy()
    
    logger.info(f"Train: {len(train_df)} | Test: {len(test_df)}")
    return train_df, test_df

# ─── 1. Feature Correlation ────────────────────────────────────────────────────

def plot_correlation_matrix(df):
    """Spearman correlation heatmap of all features + target."""
    logger.info("Generating Feature Correlation Heatmap...")
    
    cols = FEATURES + [TARGET_ANOMALY]
    labels = [FEATURE_LABELS.get(f, f) for f in FEATURES] + ['LST Anomaly (K)']
    
    corr = df[cols].corr(method='spearman')
    
    plt.figure(figsize=(12, 10))
    sns.heatmap(corr, annot=True, cmap='coolwarm', fmt=".2f", vmin=-1, vmax=1,
                xticklabels=labels, yticklabels=labels)
    plt.title("Feature Correlation Matrix (Spearman)", fontsize=14)
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / "feature_correlation.png", dpi=150)
    plt.close()
    logger.info("  Saved: feature_correlation.png")

# ─── 2. Feature Importance ─────────────────────────────────────────────────────

def plot_feature_importance(model, X_test, y_test):
    """Permutation importance with error bars."""
    logger.info("Calculating Permutation Feature Importance (10 repeats)...")
    
    result = permutation_importance(
        model, X_test, y_test,
        n_repeats=10, random_state=RANDOM_STATE, n_jobs=-1
    )
    
    sorted_idx = result.importances_mean.argsort()
    labels = [FEATURE_LABELS.get(FEATURES[i], FEATURES[i]) for i in sorted_idx]
    
    plt.figure(figsize=(10, 7))
    plt.barh(range(len(sorted_idx)),
             result.importances_mean[sorted_idx],
             xerr=result.importances_std[sorted_idx],
             align='center', color='steelblue', edgecolor='black')
    plt.yticks(range(len(sorted_idx)), labels, fontsize=11)
    plt.xlabel("Permutation Importance (Drop in R²)", fontsize=12)
    plt.title("Feature Importance (Permutation-Based)", fontsize=14)
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / "feature_importance.png", dpi=150)
    plt.close()
    
    # Log ranking
    ranked = np.array(FEATURES)[sorted_idx][::-1]
    for i, feat in enumerate(ranked):
        idx = sorted_idx[::-1][i]
        logger.info(f"  #{i+1}: {FEATURE_LABELS.get(feat, feat):30s} = {result.importances_mean[idx]:.4f}")
    
    logger.info("  Saved: feature_importance.png")
    return ranked

# ─── 3. Partial Dependence Plots ───────────────────────────────────────────────

def plot_pdp(model, X_train, features_to_plot):
    """Individual PDP for each feature to allow clear interpretation."""
    logger.info(f"Generating Partial Dependence Plots for {len(features_to_plot)} features...")
    
    n_features = len(features_to_plot)
    n_cols = 2
    n_rows = (n_features + 1) // 2
    
    fig, axes = plt.subplots(n_rows, n_cols, figsize=(14, 4 * n_rows))
    axes = axes.flatten()
    
    for i, feature in enumerate(features_to_plot):
        feat_idx = list(X_train.columns).index(feature)
        
        PartialDependenceDisplay.from_estimator(
            model, X_train, [feat_idx],
            kind="average",
            n_jobs=-1,
            grid_resolution=50,
            ax=axes[i]
        )
        
        axes[i].set_title(FEATURE_LABELS.get(feature, feature), fontsize=12)
        axes[i].set_ylabel("Effect on LST Anomaly (K)")
    
    # Hide unused axes
    for j in range(n_features, len(axes)):
        axes[j].set_visible(False)
    
    fig.suptitle("Partial Dependence Plots\nHow each feature independently affects temperature", 
                 fontsize=14, y=1.02)
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / "partial_dependence_plots.png", dpi=150, bbox_inches='tight')
    plt.close()
    logger.info("  Saved: partial_dependence_plots.png")

# ─── 4. Spatial Error Map ──────────────────────────────────────────────────────

def plot_spatial_error(model, test_df):
    """Maps residuals (Actual - Predicted) to reveal spatial bias."""
    logger.info("Generating Spatial Error Map...")
    
    X_test = test_df[FEATURES]
    y_test = test_df[TARGET_ANOMALY]
    
    y_pred = model.predict(X_test)
    residuals = y_test.values - y_pred
    rmse = np.sqrt(mean_squared_error(y_test, y_pred))
    r2 = r2_score(y_test, y_pred)
    
    logger.info(f"  Test RMSE: {rmse:.2f} K | R²: {r2:.3f}")
    
    plt.figure(figsize=(12, 10))
    sc = plt.scatter(test_df['pixel_x'], test_df['pixel_y'],
                     c=residuals, cmap='coolwarm',
                     s=3, alpha=0.8, vmin=-5, vmax=5)
    cbar = plt.colorbar(sc, shrink=0.8)
    cbar.set_label("Residual (K)\nRed = Hotter than predicted | Blue = Cooler than predicted", fontsize=10)
    plt.axis('equal')
    plt.title(f"Spatial Error Map (Test Set)\nRMSE = {rmse:.2f} K | R² = {r2:.3f}", fontsize=14)
    plt.xlabel("UTM X (m)")
    plt.ylabel("UTM Y (m)")
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / "spatial_error_map.png", dpi=150)
    plt.close()
    logger.info("  Saved: spatial_error_map.png")

# ─── Main ──────────────────────────────────────────────────────────────────────

def main():
    # 1. Load Data
    train_df, test_df = load_and_prep_data()
    
    # 2. Load Model
    model_path = MODELS_DIR / "gb_model_anomaly.joblib"
    if not model_path.exists():
        logger.error(f"No model found at {model_path}. Run phase2b_model.py first.")
        return
    
    logger.info(f"Loading Model: {model_path.name}")
    model = joblib.load(model_path)
    
    # 3. Correlation Matrix (Full Data)
    plot_correlation_matrix(pd.concat([train_df, test_df]))
    
    # 4. Feature Importance (Test Data)
    X_test = test_df[FEATURES]
    y_test = test_df[TARGET_ANOMALY]
    ranked_features = plot_feature_importance(model, X_test, y_test)
    
    # 5. Partial Dependence Plots (All features)
    plot_pdp(model, train_df[FEATURES], list(ranked_features))
    
    # 6. Spatial Error Map
    plot_spatial_error(model, test_df)
    
    logger.info(f"Interpretation complete. All plots saved to: {OUTPUT_DIR}")

if __name__ == "__main__":
    main()
