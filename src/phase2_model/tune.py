
import pandas as pd
import numpy as np
import logging
from pathlib import Path
import joblib
from itertools import product
import lightgbm as lgb
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
BLOCK_SIZE = 5000 # used to prevent spatial leakeage from learning from nearby pixels
TEST_RATIO = 0.3
RANDOM_STATE = 42

FEATURES = [
    'ndvi_mean',
    'ndvi_std',
    'albedo_mean',
    'albedo_std',
    'building_density_mean',
    'building_density_std',
    'height_mean',
    'height_std',
    'road_density_mean',
    'road_density_std',
    'sand_mask_fraction',
    'water_mask_full_fraction',
    'dist_to_coast_m'
]

TARGET_RAW = 'viirs_lst'
TARGET_ANOMALY = 'lst_anomaly'

# Hyperparameter Distributions - Using Continuous/Discrete Distributions
# This allows the script to explore values "in between" fixed grid points.
from scipy.stats import uniform, randint, loguniform

# Define distributions to sample from
PARAM_DISTRIBUTIONS = {
    'learning_rate':    loguniform(0.01, 0.3),            # Explore small & large rates efficiently - log distfavours samller values
    'n_estimators':     randint(500, 3000),               # Trees: 500 to 3000
    'max_depth':        randint(3, 16),                   # Depth: 3 to 15 (None handling done carefully)
    'min_child_samples':randint(10, 100),                 # Smoothness
    'num_leaves':       randint(31, 255),                 # Complexity
    'reg_lambda':       uniform(0, 10),                   # L2 Regularization
    'reg_alpha':        uniform(0, 10),                   # L1 Regularization
    'subsample':        uniform(0.5, 0.5),                # Bagging fraction (0.5 to 1.0)
    'colsample_bytree': uniform(0.5, 0.5)                 # Feature fraction (0.5 to 1.0)
}

def load_data():
    logger.info("Loading Data...")
    df = pd.read_csv(INPUT_FILE)
    
    # Calculate Anomaly
    scene_means = df.groupby('scene_id')[TARGET_RAW].transform('mean') # Avg temp per scene
    df[TARGET_ANOMALY] = df[TARGET_RAW] - scene_means # Calculating avg anamoly by subbing the avg temp from the temp
    
    return df

def create_spatial_cv_folds(df, n_folds=10):  # Expanded from 5 to 10 folds
    """
    Creates Spatial Cross-Validation folds based on block assignments.
    Each fold uses a different set of spatial blocks as the validation set.
    This prevents data leakage from spatial autocorrelation.
    """
    logger.info(f"Creating {n_folds}-Fold Spatial Cross-Validation...")
    
    df['block_x'] = (df['pixel_x'] // BLOCK_SIZE).astype(int)
    df['block_y'] = (df['pixel_y'] // BLOCK_SIZE).astype(int)
    
    blocks = df[['block_x', 'block_y']].drop_duplicates() # Gets a df of all the boxes which kinda represents the grid of all the blocks
    
    np.random.seed(RANDOM_STATE)
    shuffled_blocks = blocks.sample(frac=1, random_state=RANDOM_STATE).reset_index(drop=True)
    
    # Assign each block to a particular fold
    fold_assignments = {}
    for i, (_, row) in enumerate(shuffled_blocks.iterrows()):
        fold_assignments[(row['block_x'], row['block_y'])] = i % n_folds
    
    df['fold'] = df.apply(lambda row: fold_assignments[(row['block_x'], row['block_y'])], axis=1)
    
    logger.info(f"Fold sizes: {df['fold'].value_counts().sort_index().to_dict()}")
    
    return df

def evaluate_params(df, params):
    """
    Evaluates a single hyperparameter combination using Spatial CV.
    Returns the mean R² and mean RMSE across folds.
    """
    n_folds = df['fold'].nunique()
    r2_scores = []
    rmse_scores = []
    
    active_folds = range(n_folds) 
    
    for fold in active_folds:
        val_mask = df['fold'] == fold
        # Training: all data not in that fold, Validation: all data in that fold
        X_train = df.loc[~val_mask, FEATURES]
        y_train = df.loc[~val_mask, TARGET_ANOMALY]
        X_val = df.loc[val_mask, FEATURES]
        y_val = df.loc[val_mask, TARGET_ANOMALY]
        
        model = lgb.LGBMRegressor(
            random_state=RANDOM_STATE,
            n_jobs=-1,
            verbose=-1,
            **params
        )
        model.fit(
            X_train, y_train,
            eval_set=[(X_val, y_val)],
            callbacks=[lgb.early_stopping(stopping_rounds=20, verbose=False)],
        )
        
        y_pred = model.predict(X_val)
        r2_scores.append(r2_score(y_val, y_pred))
        rmse_scores.append(np.sqrt(mean_squared_error(y_val, y_pred)))
    
    return np.mean(r2_scores), np.mean(rmse_scores)

def sample_params(n_samples):
    """Generates n_samples parameter dictionaries from distributions."""
    np.random.seed(RANDOM_STATE)
    samples = []
    for _ in range(n_samples):
        params = {}
        for k, v in PARAM_DISTRIBUTIONS.items():
            if hasattr(v, 'rvs'): # If it's a scipy distribution - should be randomly sampled from the distribution
                params[k] = v.rvs(random_state=np.random.randint(0, 10000))
            else: # It's a fixed primitive value
                params[k] = v
        samples.append(params)
    return samples

def run_tuning():
    # Load & Prep
    df = load_data()
    df = create_spatial_cv_folds(df, n_folds=10) # 10 distinct spatial zones
    
    # Generate 100 random combinations from continuous distributions
    n_combos = 100
    sampled_combos = sample_params(n_combos)
    
    logger.info(f"Starting Robust Randomized Search with {n_combos} iterations...")
    logger.info(f"Using {len(FEATURES)} features (including _std texture features)")
    logger.info("Parameters are sampled from continuous distributions (not a fixed grid).")
    logger.info("Default baseline: n_estimators=500, lr=0.05 | R²≈0.54, RMSE≈2.39 K")
    logger.info("-" * 80)
    
    best_r2 = -np.inf
    best_rmse = np.inf
    best_params = None
    results = []
    
    # iterate through all the sampled combinations of parameters
    for i, params in enumerate(sampled_combos):
        
        try:
            # for each set of parametres find the R2 and RMSE score
            r2, rmse = evaluate_params(df, params)
            results.append((r2, rmse, params))
            
            is_new_best = r2 > best_r2
            if is_new_best:
                best_r2 = r2
                best_rmse = rmse
                best_params = params
            
            marker = " ★ NEW BEST" if is_new_best else ""
            
            # Compact param summary: only show the key hyperparams
            short = f"lr={params['learning_rate']:.4f} trees={params['n_estimators']} depth={params['max_depth']} leaves={params['num_leaves']}"
            logger.info(f"[{i+1:3d}/{n_combos}] R²={r2:.4f} | RMSE={rmse:.3f} K | {short}{marker}")
        except Exception as e:
            logger.warning(f"[{i+1:3d}/{n_combos}] FAILED: {e}")
    
    # Sort by R² descending
    results.sort(key=lambda x: x[0], reverse=True)
    
    logger.info("=" * 80)
    logger.info("HYPERPARAMETER TUNING COMPLETE")
    logger.info("=" * 80)
    logger.info(f"Best CV R²:   {best_r2:.4f}")
    logger.info(f"Best CV RMSE: {best_rmse:.3f} K")
    logger.info("")
    logger.info("Top 5 Configurations:")
    logger.info(f"  {'Rank':<6} {'R²':<10} {'RMSE':<10} {'LR':<10} {'Trees':<8} {'Depth':<8} {'Leaves':<8}")
    logger.info(f"  {'-'*60}")
    for rank, (r2, rmse, params) in enumerate(results[:5], 1):
        logger.info(f"  #{rank:<5} {r2:<10.4f} {rmse:<10.3f} {params['learning_rate']:<10.4f} {params['n_estimators']:<8} {params['max_depth']:<8} {params['num_leaves']:<8}")
    
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
    
    final_model = lgb.LGBMRegressor(
        random_state=RANDOM_STATE,
        n_jobs=-1,
        **best_params
    )
    # Re-split 10% for final early stopping
    from sklearn.model_selection import train_test_split
    X_f_tr, X_f_val, y_f_tr, y_f_val = train_test_split(train_df[FEATURES], train_df[TARGET_ANOMALY], test_size=0.1, random_state=RANDOM_STATE)
    
    final_model.fit(
        X_f_tr, y_f_tr,
        eval_set=[(X_f_val, y_f_val)],
        callbacks=[lgb.early_stopping(stopping_rounds=20, verbose=False)]
    )
    
    y_pred = final_model.predict(test_df[FEATURES])
    rmse = np.sqrt(mean_squared_error(test_df[TARGET_ANOMALY], y_pred))
    r2 = r2_score(test_df[TARGET_ANOMALY], y_pred)
    
    logger.info(f"FINAL Test RMSE: {rmse:.3f} K")
    logger.info(f"FINAL Test R²:   {r2:.3f}")
    logger.info("=" * 60)
    
    # Save only the parameters, let train.py build the final model
    joblib.dump(best_params, MODELS_DIR / "best_params.joblib")
    logger.info(f"Best parameters saved to {MODELS_DIR / 'best_params.joblib'}")

if __name__ == "__main__":
    run_tuning()
