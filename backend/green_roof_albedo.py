"""
Find the albedo value that corresponds to NDVI ~0.28 (green roof target).
Queries our own raster data for pixels in the green roof NDVI range.
"""
import os
import rasterio
import numpy as np

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "final", "phase1_features")

ndvi = rasterio.open(f"{DATA}/ndvi_30m.tif").read(1).astype(float)
albedo = rasterio.open(f"{DATA}/albedo_30m.tif").read(1).astype(float)
sand = rasterio.open(f"{DATA}/sand_mask_30m.tif").read(1).astype(float)
water = rasterio.open(f"{DATA}/water_mask_full_30m.tif").read(1).astype(float)

# Valid pixels (no nodata)
valid = ~np.isnan(ndvi) & ~np.isnan(albedo) & (ndvi > -9999) & (albedo > -9999)

print("=" * 60)
print("GREEN ROOF ALBEDO ANALYSIS")
print("Finding albedo at different NDVI levels (non-sand, non-water)")
print("=" * 60)

# For each NDVI band, find the corresponding albedo
bands = [
    (0.25, 0.31)
]

for lo, hi in bands:
    mask = valid & (ndvi >= lo) & (ndvi < hi) & (sand == 0) & (water == 0)
    label = f"NDVI [{lo:.2f}, {hi:.2f})"
    
    count = mask.sum()
    if count > 0:
        a_mean = albedo[mask].mean()
        a_median = np.median(albedo[mask])
        a_std = albedo[mask].std()
        n_mean = ndvi[mask].mean()
        print(f"\n  {label}: {count:,} pixels")
        print(f"    Albedo:  mean={a_mean:.4f}  median={a_median:.4f}  std={a_std:.4f}")
        print(f"    NDVI:    mean={n_mean:.4f}")
    else:
        print(f"\n  {label}: 0 pixels")

print("\n" + "=" * 60)
print("CONCLUSION: Look at the albedo for the NDVI [0.25, 0.31) band")
print("That's your green roof albedo target.")
print("=" * 60)
