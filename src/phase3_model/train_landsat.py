import pandas as pd
import numpy as np
import logging
from pathlib import Path
import json
import matplotlib.pyplot as plt

from sklearn.dummy import DummyRegressor
from sklearn.metrics import mean_squared_error, r2_score
from sklearn.model_selection import train_test_split
import lightgbm as lgb
import joblib

# Setup Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Paths
DATA_DIR = Path("data/final")
INPUT_FILE = DATA_DIR / "phase3a_training_table.csv"
OUTPUT_DIR = Path("data/model_outputs/phase3a")
MODELS_DIR = Path("data/models")

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
MODELS_DIR.mkdir(parents=True, exist_ok=True)

# Configuration
BLOCK_SIZE = 5000  # 5km blocks
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
TARGET_RAW = 'landsat_lst'
TARGET_ANOMALY = 'lst_anomaly_landsat'

def add_lst_anomaly(df):
    """
    Calculates LST Anomaly: Pixel Temp - Scene Average Temp.
    This normalizes for day-to-day weather variations.
    """
    logger.info("Calculating LST Anomalies (Normalizing for Weather)...")
    
    # Calculate mean LST per scene
    scene_means = df.groupby('scene_id')[TARGET_RAW].transform('mean')
    
    # Calculate Anomaly
    df[TARGET_ANOMALY] = df[TARGET_RAW] - scene_means
    
    logger.info(f"Landsat LST Mean Range: {scene_means.min():.2f}K to {scene_means.max():.2f}K")
    logger.info(f"Anomaly Range:  {df[TARGET_ANOMALY].min():.2f}K to {df[TARGET_ANOMALY].max():.2f}K")
    
    return df

def create_block_split(df):
    """
    Splits data based on 5km spatial blocks to prevent leakage
    and ensure generalization.
    """
    logger.info(f"Creating Spatial Split using {BLOCK_SIZE}m Blocks...")
    
    # Assign Block IDs
    df['block_x'] = (df['pixel_x'] // BLOCK_SIZE).astype(int)
    df['block_y'] = (df['pixel_y'] // BLOCK_SIZE).astype(int)
    
    # Create unique block identifier
    blocks = df[['block_x', 'block_y']].drop_duplicates()
    
    # Randomly assign blocks to Test set
    np.random.seed(RANDOM_STATE)
    shuffled_blocks = blocks.sample(frac=1, random_state=RANDOM_STATE).reset_index(drop=True)
    
    # Split blocks, not pixels
    n_test_blocks = int(len(blocks) * TEST_RATIO)
    test_blocks_df = shuffled_blocks.iloc[:n_test_blocks]
    
    # Create Mask array using incredibly fast vectorized merge
    test_blocks_df = test_blocks_df.copy()
    test_blocks_df['is_test'] = True
    
    df = df.merge(test_blocks_df, on=['block_x', 'block_y'], how='left')
    df['is_test'] = df['is_test'].fillna(False)
    
    train_df = df[~df['is_test']].copy()
    test_df = df[df['is_test']].copy()
    
    logger.info("-" * 30)
    logger.info(f"Total Blocks: {len(blocks)}")
    logger.info(f"Test Blocks:  {len(test_blocks_df)}")
    logger.info(f"Train Samples: {len(train_df):,} ({len(train_df)/len(df):.1%})")
    logger.info(f"Test Samples:  {len(test_df):,} ({len(test_df)/len(df):.1%})")
    logger.info("-" * 30)
    
    return train_df, test_df

def load_data(input_file):
    """
    Loads the massive 24M row CSV efficiently by explicitly defining float32 types.
    """
    logger.info(f"Loading large CSV dataset: {input_file}")
    df = pd.read_csv(input_file, dtype={
        'pixel_x': np.float32,
        'pixel_y': np.float32,
        'scene_id': str,
        'landsat_lst': np.float32,
        'ndvi_mean': np.float32,
        'ndvi_std': np.float32,
        'albedo_mean': np.float32,
        'albedo_std': np.float32,
        'building_density_mean': np.float32,
        'building_density_std': np.float32,
        'height_mean': np.float32,
        'height_std': np.float32,
        'road_density_mean': np.float32,
        'road_density_std': np.float32,
        'sand_mask_fraction': np.float32,
        'water_mask_full_fraction': np.float32,
        'dist_to_coast_m': np.float32
    })
    
    return df

def visualize_split(train_df, test_df):
    """
    Generates a scatter plot of the split.
    """
    plt.figure(figsize=(10, 10))
    # Plot Train
    plt.scatter(train_df['pixel_x'], train_df['pixel_y'], c='blue', s=2, alpha=0.6, label='Train Blocks')
    # Plot Test
    plt.scatter(test_df['pixel_x'], test_df['pixel_y'], c='red', s=2, alpha=0.6, label='Test Blocks')
    
    plt.axis('equal')
    plt.legend()
    plt.title(f"Block Spatial Split ({BLOCK_SIZE}m)")
    plt.xlabel("UTM X")
    plt.ylabel("UTM Y")
    
    output_path = OUTPUT_DIR / "block_split_visualization.png"
    plt.savefig(output_path)
    logger.info(f"Visualization saved to {output_path}")

def train_model(train_df, test_df):
    """
    Trains HistGradientBoosting on Landsat LST Anomaly.
    """
    target = TARGET_ANOMALY
    
    X_train = train_df[FEATURES]
    y_train = train_df[target]
    X_test = test_df[FEATURES]
    y_test = test_df[target]
    
    logger.info(f"Training on Target: {target}")
    
    # 1. Baseline
    dummy = DummyRegressor(strategy="mean")
    dummy.fit(X_train, y_train)
    y_pred_dummy = dummy.predict(X_test)
    rmse_dummy = np.sqrt(mean_squared_error(y_test, y_pred_dummy))
    logger.info(f"Baseline (Mean) RMSE: {rmse_dummy:.2f} K")
    
    # 2. Train LightGBM Model
    params_path = MODELS_DIR / "best_params_landsat.joblib"
    if params_path.exists():
        logger.info(f"Loading tuned hyperparameters from {params_path.name}...")
        best_params = joblib.load(params_path)
        gb = lgb.LGBMRegressor(
            random_state=RANDOM_STATE,
            n_jobs=-1,
            verbose=-1,
            **best_params
        )
    else:
        logger.info("Training LGBMRegressor with DEFAULT parameters (no tuned params found)...")
        gb = lgb.LGBMRegressor(
            n_estimators=500,
            learning_rate=0.05,
            random_state=RANDOM_STATE,
            n_jobs=-1,
            verbose=-1
        )
    
    # Inner split for early stopping
    X_tr_inner, X_val_inner, y_tr_inner, y_val_inner = train_test_split(
        X_train, y_train, test_size=0.1, random_state=RANDOM_STATE
    )
    
    gb.fit(
        X_tr_inner, y_tr_inner,
        eval_set=[(X_val_inner, y_val_inner)],
        callbacks=[lgb.early_stopping(stopping_rounds=20, verbose=False)]
    )
    
    # 3. Evaluate
    y_pred = gb.predict(X_test)
    rmse = np.sqrt(mean_squared_error(y_test, y_pred))
    r2 = r2_score(y_test, y_pred)
    
    logger.info("-" * 30)
    logger.info("FINAL RESULTS (LANDSAT LST ANOMALY - GRADIENT BOOSTING)")
    logger.info(f"Test RMSE: {rmse:.2f} K")
    logger.info(f"Test R²:   {r2:.2f}")
    logger.info(f"Improvement over Baseline: {rmse_dummy - rmse:.2f} K")
    logger.info("-" * 30)
    
    # Save Model
    joblib.dump(gb, MODELS_DIR / "gb_model_landsat.joblib")
    logger.info(f"Model saved to {MODELS_DIR / 'gb_model_landsat.joblib'}")
    
    # Feature Importances (permutation importance approximation natively not available in HistGB, but we can print the features used)
    logger.info(f"Model used {gb.n_features_in_} features.")
    
    return gb

def main():
    if not INPUT_FILE.exists():
        logger.error(f"Input file not found: {INPUT_FILE}")
        return
        
    # Create required directory structure
    (Path("src") / "phase3_model").mkdir(parents=True, exist_ok=True)
    
    # 1. Load Data
    df = load_data(INPUT_FILE)
    
    # 2. Add Anomaly
    df = add_lst_anomaly(df)
    
    # 3. Block Split
    train_df, test_df = create_block_split(df)
    
    # 4. Visualize Split
    visualize_split(train_df, test_df)
    
    # 5. Train Model
    train_model(train_df, test_df)

if __name__ == "__main__":
    main()
