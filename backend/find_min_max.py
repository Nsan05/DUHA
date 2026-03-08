"""
Find min and max values for all 8 backend features from the base rasters.
"""
import os
import rasterio
import numpy as np

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "final", "phase1_features")

features = {
    "ndvi_mean": "ndvi_30m.tif",
    "albedo_mean": "albedo_30m.tif",
    "building_density_mean": "building_density_30m.tif",
    "height_mean": "height_30m.tif",
    "road_density_mean": "road_density_30m.tif",
    "sand_mask_fraction": "sand_mask_30m.tif",
    "water_mask_full_fraction": "water_mask_full_30m.tif",
    "dist_to_coast_m": "dist_to_coast_30m.tif"
}

print("=" * 50)
print("FEATURE MIN/MAX ANALYSIS")
print("=" * 50)

for name, filename in features.items():
    path = os.path.join(DATA, filename)
    if not os.path.exists(path):
        print(f"Missing file: {filename}")
        continue
        
    with rasterio.open(path) as src:
        data = src.read(1).astype(float)
        
        # Filter out nodata and NaN
        if src.nodata is not None:
            valid_mask = (data != src.nodata) & ~np.isnan(data)
        else:
            # Assume extreme negative values are nodata if no explicit nodata
            valid_mask = (data > -9999) & ~np.isnan(data)
            
        valid_data = data[valid_mask]
        
        if len(valid_data) > 0:
            f_min = valid_data.min()
            f_max = valid_data.max()
            print(f"{name:25s} | Min: {f_min:>8.4f} | Max: {f_max:>8.4f}")
        else:
            print(f"{name:25s} | No valid data")

print("=" * 50)
