
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

# Configuration from Training Script
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
    'water_mask_full_fraction'
]
TARGET_RAW = 'viirs_lst'
TARGET_ANOMALY = 'lst_anomaly'

def load_and_prep_data():
    """
    Loads data and recreates the Training/Test split exactly as Phase 2B.
    """
    logger.info("Loading Data...")
    df = pd.read_csv(INPUT_FILE)
    
    # Re-calculate Anomaly (as it wasn't saved to disk)
    logger.info("Recalculating LST Anomalies...")
    scene_means = df.groupby('scene_id')[TARGET_RAW].transform('mean')
    df[TARGET_ANOMALY] = df[TARGET_RAW] - scene_means
    
    # Re-create Spatial Split
    logger.info(f"Recreating Spatial Split ({BLOCK_SIZE}m blocks)...")
    df['block_x'] = (df['pixel_x'] // BLOCK_SIZE).astype(int)
    df['block_y'] = (df['pixel_y'] // BLOCK_SIZE).astype(int)
    
    blocks = df[['block_x', 'block_y']].drop_duplicates()
    
    # Deterministic Shuffle
    np.random.seed(RANDOM_STATE)
    shuffled_blocks = blocks.sample(frac=1, random_state=RANDOM_STATE).reset_index(drop=True)
    
    n_test_blocks = int(len(blocks) * TEST_RATIO)
    test_blocks_df = shuffled_blocks.iloc[:n_test_blocks]
    test_blocks_set = set(zip(test_blocks_df['block_x'], test_blocks_df['block_y']))
    
    df['is_test'] = df.apply(lambda row: (row['block_x'], row['block_y']) in test_blocks_set, axis=1)
    
    train_df = df[~df['is_test']].copy()
    test_df = df[df['is_test']].copy()
    
    return train_df, test_df

def plot_correlation_matrix(df):
    """
    Generates a Heatmap of Feature Correlations.
    """
    logger.info("Generating Feature Correlation Heatmap...")
    
    # Select Features + Target
    cols = FEATURES + [TARGET_ANOMALY]
    corr = df[cols].corr(method='spearman') # Spearman for non-linear relationships
    
    plt.figure(figsize=(10, 8))
    sns.heatmap(corr, annot=True, cmap='coolwarm', fmt=".2f", vmin=-1, vmax=1)
    plt.title("Feature Correlation Matrix (Spearman)")
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / "feature_correlation.png")
    plt.close()

def plot_feature_importance(model, X_test, y_test):
    """
    Calculates and plots Permutation Importance.
    """
    logger.info("Calculating Permutation Feature Importance...")
    
    result = permutation_importance(
        model, X_test, y_test, 
        n_repeats=10, random_state=RANDOM_STATE, n_jobs=-1
    )
    
    sorted_idx = result.importances_mean.argsort()
    
    plt.figure(figsize=(10, 6))
    plt.barh(range(len(sorted_idx)), result.importances_mean[sorted_idx], align='center')
    plt.yticks(range(len(sorted_idx)), np.array(FEATURES)[sorted_idx])
    plt.xlabel("Permutation Importance (Drop in R²)")
    plt.title("Feature Importance (Permutation)")
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / "feature_importance.png")
    plt.close()
    
    return np.array(FEATURES)[sorted_idx][::-1] # Return ranked features

def plot_pdp(model, X_train, features_to_plot):
    """
    Generates Partial Dependence Plots for top features.
    """
    logger.info("Generating Partial Dependence Plots...")
    
    fig, ax = plt.subplots(figsize=(12, 4 * ((len(features_to_plot) // 3) + 1)))
    
    PartialDependenceDisplay.from_estimator(
        model, X_train, features_to_plot,
        kind="average",
        n_jobs=-1,
        grid_resolution=50
    ).plot(ax=ax)
    
    plt.suptitle("Partial Dependence Plots (Effect on LST Anomaly K)", y=1.02)
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / "partial_dependence_plots.png", bbox_inches='tight')
    plt.close()

def plot_spatial_error(model, test_df):
    """
    Plots the residuals (Actual - Predicted) on the map.
    """
    logger.info("Generating Spatial Error Map...")
    
    X_test = test_df[FEATURES]
    y_test = test_df[TARGET_ANOMALY]
    
    y_pred = model.predict(X_test)
    test_df['residual'] = y_test - y_pred  # Positive = Model Underestimated Heat
    
    plt.figure(figsize=(12, 10))
    sc = plt.scatter(test_df['pixel_x'], test_df['pixel_y'], 
                     c=test_df['residual'], cmap='coolwarm', 
                     s=2, alpha=0.8, vmin=-5, vmax=5)
    plt.colorbar(sc, label="Residual Error (K)\n(Red = Hotter than Predicted)")
    plt.axis('equal')
    plt.title("Spatial Error Map (Test Set Residuals)")
    plt.xlabel("UTM X")
    plt.ylabel("UTM Y")
    plt.savefig(OUTPUT_DIR / "spatial_error_map.png")
    plt.close()

def main():
    # 1. Load Data
    train_df, test_df = load_and_prep_data()
    
    # 2. Load Model
    model_path = MODELS_DIR / "gb_model_anomaly.joblib"
    if not model_path.exists():
        logger.error(f"Model not found at {model_path}. Run Phase 2B Step 2 first.")
        return
        
    logger.info(f"Loading Model from {model_path}...")
    model = joblib.load(model_path)
    
    # 3. Correlation Matrix (on Full Data)
    plot_correlation_matrix(pd.concat([train_df, test_df]))
    
    # 4. Feature Importance (on Test Data)
    X_test = test_df[FEATURES]
    y_test = test_df[TARGET_ANOMALY]
    ranked_features = plot_feature_importance(model, X_test, y_test)
    logger.info(f"Top 3 Features: {ranked_features[:3]}")
    
    # 5. Partial Dependence Plots (Top 4 Features)
    plot_pdp(model, train_df[FEATURES], ranked_features[:4])
    
    # 6. Spatial Error Map
    plot_spatial_error(model, test_df)
    
    logger.info(f"Interpretation complete. Outputs saved to {OUTPUT_DIR}")

if __name__ == "__main__":
    main()
