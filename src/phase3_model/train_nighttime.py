import pandas as pd
import numpy as np
import logging
from pathlib import Path
import json
import matplotlib.pyplot as plt

from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.dummy import DummyRegressor
from sklearn.metrics import mean_squared_error, r2_score
import joblib

# Setup Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Paths
DATA_DIR = Path("data/final")
INPUT_FILE = DATA_DIR / "phase3b_training_table.csv"
OUTPUT_DIR = Path("data/model_outputs/phase3b")
MODELS_DIR = Path("data/models")

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
MODELS_DIR.mkdir(parents=True, exist_ok=True)

# Configuration
BLOCK_SIZE = 5000  # 5km blocks
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

def add_lst_anomaly(df):
    """
    Calculates LST Anomaly: Pixel Temp - Scene Average Temp.
    This normalizes for weather variations across different nights.
    """
    logger.info("Calculating LST Anomalies (Normalizing for Weather)...")
    
    # Calculate mean LST per scene
    scene_means = df.groupby('scene_id')[TARGET_RAW].transform('mean')
    
    # Calculate Anomaly
    df[TARGET_ANOMALY] = df[TARGET_RAW] - scene_means
    
    logger.info(f"Nighttime LST Mean Range: {scene_means.min():.2f}K to {scene_means.max():.2f}K")
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
    
    # Create Mask
    test_blocks_set = set(zip(test_blocks_df['block_x'], test_blocks_df['block_y']))
        
    # Apply mask
    df['is_test'] = df.apply(lambda row: (row['block_x'], row['block_y']) in test_blocks_set, axis=1)
    
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
    Loads Phase 3B training data. Note: only ~40k rows so dtype optimizations are optional, 
    but included for safety.
    """
    logger.info(f"Loading dataset: {input_file}")
    df = pd.read_csv(input_file)
    
    # Just in case there are missing values in features
    df = df.dropna(subset=FEATURES + [TARGET_RAW])
    return df

def visualize_split(train_df, test_df):
    """
    Generates a scatter plot of the split.
    """
    plt.figure(figsize=(10, 10))
    # Plot Train
    plt.scatter(train_df['pixel_x'], train_df['pixel_y'], c='blue', s=20, alpha=0.6, label='Train Blocks')
    # Plot Test
    plt.scatter(test_df['pixel_x'], test_df['pixel_y'], c='red', s=20, alpha=0.6, label='Test Blocks')
    
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
    Trains HistGradientBoosting on Nighttime LST Anomaly.
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
    
    # 2. HistGradientBoosting
    # Use standard hyperparameters mimicking Phase 2 and Phase 3A
    logger.info("Training HistGradientBoostingRegressor (max_iter=500, lr=0.05)...")
    gb = HistGradientBoostingRegressor(
        max_iter=500,
        learning_rate=0.05,
        random_state=RANDOM_STATE,
        early_stopping=True
    )
    gb.fit(X_train, y_train)
    
    # 2.5 Plot Training Loss
    plt.figure(figsize=(10, 6))
    # HistGradientBoostingRegressor stores the negative of the loss in train_score_ and validation_score_
    # We multiply by -1 to plot the actual loss which will go down over iterations.
    plt.plot(-np.array(gb.train_score_), label='Training Loss', color='blue', linewidth=2)
    if hasattr(gb, 'validation_score_') and len(gb.validation_score_) > 0:
        plt.plot(-np.array(gb.validation_score_), label='Validation Loss', color='orange', linewidth=2)
    plt.xlabel('Iteration (Number of Trees)')
    plt.ylabel('Loss')
    plt.title('Nighttime Model Training - Loss over Iterations')
    plt.legend()
    plt.grid(True)
    loss_plot_path = OUTPUT_DIR / "nighttime_training_loss_curve.png"
    plt.savefig(loss_plot_path)
    logger.info(f"Training loss curve saved to {loss_plot_path}")
    plt.close()
    
    # 3. Evaluate
    y_pred = gb.predict(X_test)
    rmse = np.sqrt(mean_squared_error(y_test, y_pred))
    r2 = r2_score(y_test, y_pred)
    
    logger.info("-" * 30)
    logger.info("FINAL RESULTS (NIGHTTIME LST ANOMALY - GRADIENT BOOSTING)")
    logger.info(f"Test RMSE: {rmse:.2f} K")
    logger.info(f"Test R²:   {r2:.2f}")
    logger.info(f"Improvement over Baseline: {rmse_dummy - rmse:.2f} K")
    logger.info("-" * 30)
    
    # Save Model
    joblib.dump(gb, MODELS_DIR / "gb_model_nighttime.joblib")
    logger.info(f"Model saved to {MODELS_DIR / 'gb_model_nighttime.joblib'}")
    
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
