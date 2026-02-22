import pandas as pd
import numpy as np
import logging
from pathlib import Path
import joblib

from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import mean_squared_error, r2_score
from scipy.stats import uniform, randint, loguniform

# Setup Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Paths
DATA_DIR = Path("data/final")
INPUT_FILE = DATA_DIR / "phase3b_training_table.csv"
OUTPUT_DIR = Path("data/model_outputs/phase3b")
MODELS_DIR = Path("data/models")

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
    'dist_to_coast_mean'
]

TARGET_RAW = 'nighttime_lst'
TARGET_ANOMALY = 'lst_anomaly_nighttime'

PARAM_DISTRIBUTIONS = {
    'learning_rate':    loguniform(0.01, 0.3),
    'max_iter':         randint(300, 1500),
    'max_depth':        randint(3, 16),
    'min_samples_leaf': randint(10, 80),
    'max_leaf_nodes':   randint(31, 150),
    'l2_regularization':uniform(0, 10),
    'validation_fraction':[0.1],
    'n_iter_no_change': [20],
    'early_stopping':   [True]
}

def load_data():
    logger.info("Loading Data...")
    df = pd.read_csv(INPUT_FILE)
    df = df.dropna(subset=FEATURES + [TARGET_RAW])
    scene_means = df.groupby('scene_id')[TARGET_RAW].transform('mean')
    df[TARGET_ANOMALY] = df[TARGET_RAW] - scene_means
    return df

def create_spatial_cv_folds(df, n_folds=5):
    logger.info(f"Creating {n_folds}-Fold Spatial Cross-Validation...")
    df['block_x'] = (df['pixel_x'] // BLOCK_SIZE).astype(int)
    df['block_y'] = (df['pixel_y'] // BLOCK_SIZE).astype(int)
    
    blocks = df[['block_x', 'block_y']].drop_duplicates()
    
    np.random.seed(RANDOM_STATE)
    shuffled_blocks = blocks.sample(frac=1, random_state=RANDOM_STATE).reset_index(drop=True)
    
    fold_assignments = {}
    for i, (_, row) in enumerate(shuffled_blocks.iterrows()):
        fold_assignments[(row['block_x'], row['block_y'])] = i % n_folds
    
    df['fold'] = df.apply(lambda row: fold_assignments[(row['block_x'], row['block_y'])], axis=1)
    return df

def sample_params(n_samples):
    np.random.seed(RANDOM_STATE)
    samples = []
    for _ in range(n_samples):
        params = {}
        for k, v in PARAM_DISTRIBUTIONS.items():
            if hasattr(v, 'rvs'):
                params[k] = v.rvs(random_state=np.random.randint(0, 10000))
                if isinstance(params[k], np.integer):
                    params[k] = int(params[k])
                elif isinstance(params[k], np.floating):
                    params[k] = float(params[k])
            elif isinstance(v, list):
                params[k] = v[0]
            else:
                params[k] = v
        samples.append(params)
    return samples

def evaluate_params(df, params):
    n_folds = df['fold'].nunique()
    scores_r2 = []
    scores_rmse = []
    
    for fold in range(n_folds):
        val_mask = df['fold'] == fold
        X_train = df.loc[~val_mask, FEATURES]
        y_train = df.loc[~val_mask, TARGET_ANOMALY]
        X_val = df.loc[val_mask, FEATURES]
        y_val = df.loc[val_mask, TARGET_ANOMALY]
        
        model = HistGradientBoostingRegressor(random_state=RANDOM_STATE, **params)
        model.fit(X_train, y_train)
        
        y_pred = model.predict(X_val)
        scores_r2.append(r2_score(y_val, y_pred))
        scores_rmse.append(np.sqrt(mean_squared_error(y_val, y_pred)))
    
    return np.mean(scores_r2), np.mean(scores_rmse)

def run_tuning():
    df = load_data()
    df = create_spatial_cv_folds(df, n_folds=5)
    
    n_combos = 50
    sampled_combos = sample_params(n_combos)
    
    logger.info(f"Starting Randomized Search with {n_combos} iterations...")
    
    best_score_r2 = -np.inf
    best_score_rmse = np.inf
    best_params = None
    results = []
    
    for i, params in enumerate(sampled_combos):
        try:
            mean_r2, mean_rmse = evaluate_params(df, params)
            results.append((mean_r2, mean_rmse, params))
            
            if mean_r2 > best_score_r2:
                best_score_r2 = mean_r2
                best_score_rmse = mean_rmse
                best_params = params
            
            logger.info(f"[{i+1}/{n_combos}] R²={mean_r2:.4f} | RMSE={mean_rmse:.3f} K | {params}")
        except Exception as e:
            logger.warning(f"[{i+1}/{n_combos}] FAILED: {e}")
            
    logger.info(f"Best CV R²: {best_score_r2:.4f} (RMSE: {best_score_rmse:.3f} K)")
    logger.info(f"Best Params: {best_params}")
    
    # Update train_nighttime.py automatically with best params? We will just print them and I'll update it.

if __name__ == "__main__":
    run_tuning()
