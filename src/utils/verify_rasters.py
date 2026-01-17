import rasterio
import numpy as np
import glob
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent.parent
INPUT_DIRS = [
    BASE_DIR / "data" / "intermediate" / "sentinel2_30m",
    BASE_DIR / "data" / "intermediate" / "urban_form"
]
MASK_FILE = BASE_DIR / "data" / "intermediate" / "masks" / "urban_mask_30m.tif"

def verify_rasters():
    print(f"Loading Urban Mask: {MASK_FILE.name}...")
    with rasterio.open(MASK_FILE) as src:
        urban_mask = src.read(1)
        # Ensure binary 0/1 (just in case)
        urban_mask_bool = (urban_mask == 1)
        urban_pixels_count = np.sum(urban_mask_bool)
        total_pixels = urban_mask.size
    
    print(f"Urban Mask Pixels: {urban_pixels_count:,.0f} / {total_pixels:,.0f} ({urban_pixels_count/total_pixels*100:.2f}%)")
    print("-" * 100)
    print(f"{'Filename':<25} | {'Valid Pixels':<12} | {'Raw %':<8} | {'Urban Coverage %':<18} | {'Stats (Mean)'}")
    print("-" * 100)
    
    files = []
    for d in INPUT_DIRS:
        files.extend(list(d.glob("*.tif")))
    
    for f in files:
        with rasterio.open(f) as src:
            data = src.read(1)
            
            # Dynamic Nodata Handling
            nodata_val = src.nodata
            if nodata_val is not None:
                valid_mask = (data != nodata_val) & (~np.isnan(data))
            else:
                # Fallback if no nodata defined (assume only NaN is invalid)
                valid_mask = ~np.isnan(data)
                
            valid_count = np.sum(valid_mask)
            
            # Intersection: Valid Data AND Inside Urban Mask
            intersection = valid_mask & urban_mask_bool
            intersection_count = np.sum(intersection)
            
            # Coverage: What % of the Urban Mask has valid data?
            # Ideally close to 100% (minus clouds)
            coverage_pct = (intersection_count / urban_pixels_count) * 100 if urban_pixels_count > 0 else 0
            
            # Raw %: File-wide valid data
            raw_pct = (valid_count / total_pixels) * 100
            
            # Stats of valid pixels
            mean_val = np.mean(data[valid_mask]) if valid_count > 0 else 0
            
            print(f"{f.name:<20} | {valid_count:<12,.0f} | {raw_pct:<7.2f}% | {coverage_pct:<17.2f}% | {mean_val:.4f}")

if __name__ == "__main__":
    verify_rasters()
