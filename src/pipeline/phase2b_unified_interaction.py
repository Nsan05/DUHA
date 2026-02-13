
import pandas as pd
import numpy as np
import logging
from pathlib import Path
import matplotlib.pyplot as plt
import joblib

from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.dummy import DummyRegressor
from sklearn.metrics import mean_squared_error, r2_score
from sklearn.inspection import permutation_importance

# Setup Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Paths
DATA_DIR = Path("data/final")
INPUT_FILE = DATA_DIR / "phase2_training_table_enriched.csv"
OUTPUT_DIR = Path("data/model_outputs/unified")
MODELS_DIR = Path("data/models")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
MODELS_DIR.mkdir(parents=True, exist_ok=True)

# Configuration
BLOCK_SIZE = 5000
TEST_RATIO = 0.3
RANDOM_STATE = 42
SAND_THRESHOLD = 0.95  # Filter out pixels with >95% sand

# Base Features
BASE_FEATURES = [
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

def add_lst_anomaly(df):
    """Calculates LST Anomaly (Pixel Temp - Scene Mean)."""
    logger.info("Calculating LST Anomalies...")
    scene_means = df.groupby('scene_id')[TARGET_RAW].transform('mean')
    df[TARGET_ANOMALY] = df[TARGET_RAW] - scene_means
    return df

def feature_engineering(df):
    """
    Adds Interaction Features to capture Urban Physics.
    """
    logger.info("Engineering Interaction Features...")
    
    # 1. Urban Volume (Mass) = Height * Density
    # Captures the thermal mass of concrete
    df['urban_volume'] = df['height_mean'] * df['building_density_mean']
    
    # 2. Canyon Potential = Height * Road Density
    # Captures heat trapping in streets
    df['canyon_potential'] = df['height_mean'] * df['road_density_mean']
    
    # 3. Green Cooling Efficiency = NDVI * Building Density
    # Captures the enhanced cooling of trees near buildings (shading) 
    # vs trees in the open (which just cool the ground)
    df['green_cooling'] = df['ndvi_mean'] * df['building_density_mean']
    
    # Update Feature List
    new_features = ['urban_volume', 'canyon_potential', 'green_cooling']
    all_features = BASE_FEATURES + new_features
    
    return df, all_features

def filter_data(df):
    """
    Removes Pure Desert pixels to force the model to learn Urban Form.
    """
    initial_len = len(df)
    logger.info(f"Filtering Data (Removing >{SAND_THRESHOLD:.0%} Sand)...")
    
    # Keep pixels that are NOT pure sand
    # We also remove pure water just in case, though less critical
    mask = df['sand_mask_fraction'] <= SAND_THRESHOLD
    
    df_filtered = df[mask].copy()
    
    removed = initial_len - len(df_filtered)
    logger.info(f"Removed {removed} rows ({removed/initial_len:.1%}). New Size: {len(df_filtered)}")
    
    return df_filtered

def create_block_split(df):
    """Spatial Split by 5km Blocks."""
    logger.info(f"Creating Spatial Split ({BLOCK_SIZE}m Blocks)...")
    
    df['block_x'] = (df['pixel_x'] // BLOCK_SIZE).astype(int)
    df['block_y'] = (df['pixel_y'] // BLOCK_SIZE).astype(int)
    
    blocks = df[['block_x', 'block_y']].drop_duplicates()
    
    np.random.seed(RANDOM_STATE)
    shuffled_blocks = blocks.sample(frac=1, random_state=RANDOM_STATE).reset_index(drop=True)
    
    n_test_blocks = int(len(blocks) * TEST_RATIO)
    test_blocks_df = shuffled_blocks.iloc[:n_test_blocks]
    test_blocks_set = set(zip(test_blocks_df['block_x'], test_blocks_df['block_y']))
    
    df['is_test'] = df.apply(lambda row: (row['block_x'], row['block_y']) in test_blocks_set, axis=1)
    
    train_df = df[~df['is_test']].copy()
    test_df = df[df['is_test']].copy()
    
    return train_df, test_df

def train_and_evaluate(train_df, test_df, features):
    """Trains the Unified Model and reports results."""
    logger.info(f"Training Unified Model on {len(features)} features...")
    
    X_train = train_df[features]
    y_train = train_df[TARGET_ANOMALY]
    X_test = test_df[features]
    y_test = test_df[TARGET_ANOMALY]
    
    # Baseline
    dummy = DummyRegressor(strategy="mean")
    dummy.fit(X_train, y_train)
    rmse_dummy = np.sqrt(mean_squared_error(y_test, dummy.predict(X_test)))
    
    # XGBoost (HistGradientBoosting)
    gb = HistGradientBoostingRegressor(
        max_iter=500,
        learning_rate=0.05,
        random_state=RANDOM_STATE,
        early_stopping=True
    )
    gb.fit(X_train, y_train)
    
    y_pred = gb.predict(X_test)
    rmse = np.sqrt(mean_squared_error(y_test, y_pred))
    r2 = r2_score(y_test, y_pred)
    
    logger.info("-" * 40)
    logger.info("UNIFIED MODEL RESULTS (URBAN ONLY)")
    logger.info(f"Test RMSE: {rmse:.3f} K (Baseline: {rmse_dummy:.3f} K)")
    logger.info(f"Test R²:   {r2:.3f}")
    logger.info("-" * 40)
    
    # Feature Importance
    result = permutation_importance(gb, X_test, y_test, n_repeats=5, random_state=RANDOM_STATE, n_jobs=-1)
    sorted_idx = result.importances_mean.argsort()[::-1]
    
    logger.info("FEATURE IMPORTANCE RANKING:")
    for i in sorted_idx:
        logger.info(f"  {features[i]:<25}: {result.importances_mean[i]:.4f}")
        
    # Save
    joblib.dump(gb, MODELS_DIR / "gb_model_unified.joblib")
    
    return gb

def main():
    if not INPUT_FILE.exists():
        logger.error(f"Input file not found: {INPUT_FILE}")
        return
    
    # 1. Load & Prep
    df = pd.read_csv(INPUT_FILE)
    df = add_lst_anomaly(df)
    
    # 2. Filter (The "City Envelope")
    # df = filter_data(df) # User requested to keep all pixels
    logger.info("Skipping Data Filtering (Using Full Dataset including Desert)...")
    
    # 3. Engineer Features (The "Physics")
    df, features = feature_engineering(df)
    
    # 4. Split
    train_df, test_df = create_block_split(df)
    
    # 5. Train
    train_and_evaluate(train_df, test_df, features)
    
    logger.info("Unified Model Training Complete.")

if __name__ == "__main__":
    main()
