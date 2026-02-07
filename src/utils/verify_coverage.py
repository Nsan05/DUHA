
import pandas as pd
import rasterio
from rasterio.plot import show
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path

# Paths
DATA_DIR = Path("data/final")
CSV_KEY = DATA_DIR / "phase2_training_table.csv"
MASK_PATH = Path("data/intermediate/masks/urban_mask_30m.tif")
OUTPUT_KEY = Path("data/model_outputs/coverage_map.png")

def main():
    print(f"Loading CSV: {CSV_KEY}")
    df = pd.read_csv(CSV_KEY)
    
    print(f"Loading Urban Mask: {MASK_PATH}")
    with rasterio.open(MASK_PATH) as src:
        # Read a downsampled version of the mask for plotting (10x reduction for speed)
        # The mask is approx 20km x 20km? No, Dubai is larger.
        # Check bounds
        print(f"Mask Bounds: {src.bounds}")
        
        # Calculate new shape (approx 1000 pixels wide)
        scale_factor = 0.1
        new_height = int(src.height * scale_factor)
        new_width = int(src.width * scale_factor)
        
        print(f"Reading mask with downsampling (Factor: {scale_factor})...")
        mask_data = src.read(
            1,
            out_shape=(new_height, new_width),
            resampling=rasterio.enums.Resampling.nearest
        )
        
        # Create transform for the downsampled data
        transform = src.transform * src.transform.scale(
            (src.width / mask_data.shape[1]),
            (src.height / mask_data.shape[0])
        )
        
        # Prepare Plot
        fig, ax = plt.subplots(figsize=(12, 12))
        
        # Plot Mask (Green for Urban, Transparent for 0)
        # value 1 is urban.
        # We mask out 0s
        display_mask = np.ma.masked_where(mask_data == 0, mask_data)
        
        # Use rasterio show to handle coordinates correctly
        show(display_mask, transform=transform, ax=ax, cmap='Greens', alpha=0.5, title="Data Coverage Verification")
        
        # Overlay CSV Points
        # Use simple scatter
        ax.scatter(df['pixel_x'], df['pixel_y'], c='red', s=1, alpha=0.9, label='Training Data (VIIRS)')
        
        # Formatting
        ax.set_xlabel("UTM X")
        ax.set_ylabel("UTM Y")
        ax.legend()
        ax.set_title("Urban Mask (Green) vs Training Data (Red)")
        
        # Save
        if not OUTPUT_KEY.parent.exists():
            OUTPUT_KEY.parent.mkdir(parents=True)
            
        plt.savefig(OUTPUT_KEY, dpi=300)
        print(f"Coverage Map saved to: {OUTPUT_KEY}")

if __name__ == "__main__":
    main()
