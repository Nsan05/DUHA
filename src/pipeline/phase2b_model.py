import pandas as pd
import numpy as np
import logging
from pathlib import Path
import matplotlib.pyplot as plt

# Setup Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Paths
DATA_DIR = Path("data/final")
INPUT_FILE = DATA_DIR / "phase2_training_table.csv"
OUTPUT_DIR = Path("data/model_outputs")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

def load_and_split_data(csv_path, split_ratio=0.7):
    """
    Loads data and performs a spatial split based on the X-coordinate.
    """
    logger.info(f"Loading data from {csv_path}...")
    df = pd.read_csv(csv_path)
    
    # 1. Sort by X coordinate (West to East)
    df = df.sort_values('pixel_x')
    
    # 2. Determine Split Threshold
    
    split_threshold = df['pixel_x'].quantile(split_ratio)
    logger.info(f"Spatial Split Threshold (X-Coordinate): {split_threshold:.2f}")
    
    # 3. Create Masks
    train_mask = df['pixel_x'] < split_threshold
    test_mask = df['pixel_x'] >= split_threshold
    
    train_df = df[train_mask]
    test_df = df[test_mask]
    
    # 4. Verification Stats
    logger.info("-" * 30)
    logger.info(f"Total Samples: {len(df)}")
    logger.info(f"Training Samples: {len(train_df)} ({len(train_df)/len(df):.1%})")
    logger.info(f"Testing Samples:  {len(test_df)} ({len(test_df)/len(df):.1%})")
    logger.info("-" * 30)
    
    # Check for Leakage (Range Overlap)
    max_train_x = train_df['pixel_x'].max()
    min_test_x = test_df['pixel_x'].min()
    
    logger.info(f"Max Train X: {max_train_x:.2f}")
    logger.info(f"Min Test X:  {min_test_x:.2f}")
    
    if max_train_x >= min_test_x:
        logger.error("CRITICAL: LEAKAGE DETECTED! Train max X >= Test min X")
        raise ValueError("Spatial Leakage Detected")
    else:
        logger.info("SUCCESS: CLEAN SPLIT CONFIRMED. No spatial overlap.")
        logger.info("-" * 30)
        
    return train_df, test_df

def visualize_split(train_df, test_df):
    """
    Generates a scatter plot of the split.
    """
    plt.figure(figsize=(10, 10))
    plt.scatter(train_df['pixel_x'], train_df['pixel_y'], c='blue', s=2, alpha=0.8, label='Train (West)')
    plt.scatter(test_df['pixel_x'], test_df['pixel_y'], c='red', s=2, alpha=0.8, label='Test (East)')
    plt.axis('equal')
    plt.legend()
    plt.title("Spatial Split Verification: West vs East")
    plt.xlabel("UTM X (meters)")
    plt.ylabel("UTM Y (meters)")
    
    output_path = OUTPUT_DIR / "spatial_split_visualization.png"
    plt.savefig(output_path)
    logger.info(f"Visualization saved to {output_path}")

def main():
    if not INPUT_FILE.exists():
        logger.error(f"Input file not found: {INPUT_FILE}")
        return
        
    train_df, test_df = load_and_split_data(INPUT_FILE)
    visualize_split(train_df, test_df)

if __name__ == "__main__":
    main()
