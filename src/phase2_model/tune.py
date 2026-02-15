
import pandas as pd
import numpy as np
import logging
from pathlib import Path
import joblib
from itertools import product

from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import mean_squared_error, r2_score

# Setup Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Paths
DATA_DIR = Path("data/final")
INPUT_FILE = DATA_DIR / "phase2_training_table_enriched.csv"
OUTPUT_DIR = Path("data/model_outputs")
MODELS_DIR = Path("data/models")

# Configuration (same as phase2b_model.py)
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

TARGET_RAW = 'viirs_lst'
TARGET_ANOMALY = 'lst_anomaly'

# Hyperparameter Grid
PARAM_GRID = {
    'max_iter':         [300, 500, 800],
    'learning_rate':    [0.01, 0.05, 0.1],
    'max_depth':        [4, 6, 8, None],
    'min_samples_leaf': [10, 20, 50],
    'max_leaf_nodes':   [31, 63, None],
    'l2_regularization':[0.0, 0.1, 1.0]
}

def load_data():
    logger.info("Loading Data...")
    df = pd.read_csv(INPUT_FILE)
    
    # Calculate Anomaly
    scene_means = df.groupby('scene_id')[TARGET_RAW].transform('mean')
    df[TARGET_ANOMALY] = df[TARGET_RAW] - scene_means
    
    return df

def create_spatial_cv_folds(df, n_folds=5):
    """
    Creates Spatial Cross-Validation folds based on block assignments.
    Each fold uses a different set of spatial blocks as the validation set.
    This prevents data leakage from spatial autocorrelation.
    """
    logger.info(f"Creating {n_folds}-Fold Spatial Cross-Validation...")
    
    df['block_x'] = (df['pixel_x'] // BLOCK_SIZE).astype(int)
    df['block_y'] = (df['pixel_y'] // BLOCK_SIZE).astype(int)
    
    blocks = df[['block_x', 'block_y']].drop_duplicates()
    
    np.random.seed(RANDOM_STATE)
    shuffled_blocks = blocks.sample(frac=1, random_state=RANDOM_STATE).reset_index(drop=True)
    
    # Assign each block to a fold
    fold_assignments = {}
    for i, (_, row) in enumerate(shuffled_blocks.iterrows()):
        fold_assignments[(row['block_x'], row['block_y'])] = i % n_folds
    
    df['fold'] = df.apply(lambda row: fold_assignments[(row['block_x'], row['block_y'])], axis=1)
    
    logger.info(f"Fold sizes: {df['fold'].value_counts().sort_index().to_dict()}")
    
    return df

def evaluate_params(df, params):
    """
    Evaluates a single hyperparameter combination using Spatial CV.
    Returns the mean R² across folds.
    """
    n_folds = df['fold'].nunique()
    scores = []
    
    for fold in range(n_folds):
        val_mask = df['fold'] == fold
        X_train = df.loc[~val_mask, FEATURES]
        y_train = df.loc[~val_mask, TARGET_ANOMALY]
        X_val = df.loc[val_mask, FEATURES]
        y_val = df.loc[val_mask, TARGET_ANOMALY]
        
        model = HistGradientBoostingRegressor(
            random_state=RANDOM_STATE,
            early_stopping=True,
            **params
        )
        model.fit(X_train, y_train)
        
        y_pred = model.predict(X_val)
        r2 = r2_score(y_val, y_pred)
        scores.append(r2)
    
    return np.mean(scores)

def run_tuning():
    # Load & Prep
    df = load_data()
    df = create_spatial_cv_folds(df, n_folds=5)
    
    # Generate all param combinations (sampled)
    keys = list(PARAM_GRID.keys())
    all_combos = list(product(*[PARAM_GRID[k] for k in keys]))
    
    # Random sample to keep runtime reasonable
    np.random.seed(RANDOM_STATE)
    n_combos = min(30, len(all_combos))  # Test 30 random combinations
    sampled_indices = np.random.choice(len(all_combos), n_combos, replace=False)
    sampled_combos = [all_combos[i] for i in sampled_indices]
    
    logger.info(f"Testing {n_combos} hyperparameter combinations (out of {len(all_combos)} total)...")
    
    best_score = -np.inf
    best_params = None
    results = []
    
    for i, combo in enumerate(sampled_combos):
        params = dict(zip(keys, combo))
        
        try:
            score = evaluate_params(df, params)
            results.append((score, params))
            
            if score > best_score:
                best_score = score
                best_params = params
            
            logger.info(f"[{i+1}/{n_combos}] R²={score:.4f} | {params}")
        except Exception as e:
            logger.warning(f"[{i+1}/{n_combos}] FAILED: {e}")
    
    # Sort results
    results.sort(key=lambda x: x[0], reverse=True)
    
    logger.info("=" * 60)
    logger.info("HYPERPARAMETER TUNING COMPLETE")
    logger.info("=" * 60)
    logger.info(f"Best CV R²: {best_score:.4f}")
    logger.info(f"Best Params: {best_params}")
    logger.info("")
    logger.info("Top 5 Configurations:")
    for rank, (score, params) in enumerate(results[:5], 1):
        logger.info(f"  #{rank}: R²={score:.4f} | {params}")
    
    # Final Retrain with Best Params on Full Train Set (70%)
    logger.info("=" * 60)
    logger.info("RETRAINING FINAL MODEL WITH BEST PARAMS...")
    
    # Recreate the original train/test split
    blocks = df[['block_x', 'block_y']].drop_duplicates()
    shuffled_blocks = blocks.sample(frac=1, random_state=RANDOM_STATE).reset_index(drop=True)
    n_test_blocks = int(len(blocks) * TEST_RATIO)
    test_blocks_df = shuffled_blocks.iloc[:n_test_blocks]
    test_blocks_set = set(zip(test_blocks_df['block_x'], test_blocks_df['block_y']))
    df['is_test'] = df.apply(lambda r: (r['block_x'], r['block_y']) in test_blocks_set, axis=1)
    
    train_df = df[~df['is_test']]
    test_df = df[df['is_test']]
    
    final_model = HistGradientBoostingRegressor(
        random_state=RANDOM_STATE,
        early_stopping=True,
        **best_params
    )
    final_model.fit(train_df[FEATURES], train_df[TARGET_ANOMALY])
    
    y_pred = final_model.predict(test_df[FEATURES])
    rmse = np.sqrt(mean_squared_error(test_df[TARGET_ANOMALY], y_pred))
    r2 = r2_score(test_df[TARGET_ANOMALY], y_pred)
    
    logger.info(f"FINAL Test RMSE: {rmse:.3f} K")
    logger.info(f"FINAL Test R²:   {r2:.3f}")
    logger.info("=" * 60)
    
    # Save
    joblib.dump(final_model, MODELS_DIR / "gb_model_tuned.joblib")
    joblib.dump(best_params, MODELS_DIR / "best_params.joblib")
    logger.info(f"Model saved to {MODELS_DIR / 'gb_model_tuned.joblib'}")

if __name__ == "__main__":
    run_tuning()
