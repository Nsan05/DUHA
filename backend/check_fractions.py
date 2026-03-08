"""
Comprehensive analysis of the raster data to derive intervention feature values.
Analyzes high-greenery, water, and high-building areas to get real-world reference values.
"""
import os
import rasterio
import numpy as np

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "final", "phase1_features")

# Load all rasters
sand = rasterio.open(f"{DATA}/sand_mask_30m.tif").read(1).astype(float)
water = rasterio.open(f"{DATA}/water_mask_full_30m.tif").read(1).astype(float)
bldg = rasterio.open(f"{DATA}/building_density_30m.tif").read(1).astype(float)
road = rasterio.open(f"{DATA}/road_density_30m.tif").read(1).astype(float)
ndvi = rasterio.open(f"{DATA}/ndvi_30m.tif").read(1).astype(float)
albedo = rasterio.open(f"{DATA}/albedo_30m.tif").read(1).astype(float)
height = rasterio.open(f"{DATA}/height_30m.tif").read(1).astype(float)
coast = rasterio.open(f"{DATA}/dist_to_coast_30m.tif").read(1).astype(float)

# Build valid mask (exclude nodata: ndvi=-9999, albedo=-9999, etc.)
valid = (ndvi > -100) & (albedo > -100) & (~np.isnan(sand)) & (~np.isnan(water))
print(f"Total valid pixels: {valid.sum():,}")

# ===================================================================
# 1. PARK ANALYSIS — What do high-greenery areas look like?
# ===================================================================
print("\n" + "="*70)
print("1. PARK / HIGH GREENERY ANALYSIS")
print("="*70)

# Different NDVI thresholds
for threshold in [0.15, 0.20, 0.25, 0.30, 0.35, 0.40]:
    green_mask = valid & (ndvi >= threshold)
    count = green_mask.sum()
    if count == 0:
        print(f"\n  NDVI >= {threshold}: 0 pixels")
        continue
    print(f"\n  NDVI >= {threshold}: {count:,} pixels")
    print(f"    Albedo:    mean={albedo[green_mask].mean():.4f}  median={np.median(albedo[green_mask]):.4f}  p25={np.percentile(albedo[green_mask],25):.4f}  p75={np.percentile(albedo[green_mask],75):.4f}")
    print(f"    NDVI:      mean={ndvi[green_mask].mean():.4f}  median={np.median(ndvi[green_mask]):.4f}")
    print(f"    Sand:      mean={sand[green_mask].mean():.4f}  (fraction that are sand=1: {(sand[green_mask]==1).mean()*100:.1f}%)")
    print(f"    Water:     mean={water[green_mask].mean():.4f}")
    print(f"    Building:  mean={bldg[green_mask].mean():.4f}")
    print(f"    Road:      mean={road[green_mask].mean():.4f}")
    print(f"    Height:    mean={height[green_mask].mean():.4f}")

# Parks that are on sand=0 (non-sand) and high NDVI
park_like = valid & (ndvi >= 0.30) & (sand == 0) & (water == 0)
if park_like.sum() > 0:
    print(f"\n  PARK-LIKE (NDVI>=0.30, sand=0, water=0): {park_like.sum():,} pixels")
    print(f"    Albedo:    mean={albedo[park_like].mean():.4f}  median={np.median(albedo[park_like]):.4f}  std={albedo[park_like].std():.4f}")
    print(f"    NDVI:      mean={ndvi[park_like].mean():.4f}  median={np.median(ndvi[park_like]):.4f}")
    print(f"    Building:  mean={bldg[park_like].mean():.4f}")
    print(f"    Road:      mean={road[park_like].mean():.4f}")

# ===================================================================
# 2. COOL ROAD ANALYSIS — What do high-road areas look like currently?
# ===================================================================
print("\n" + "="*70)
print("2. ROAD SURFACE ANALYSIS (for cool road baseline)")
print("="*70)

for threshold in [0.3, 0.5, 0.7]:
    road_mask = valid & (road >= threshold) & (sand == 0) & (water == 0)
    count = road_mask.sum()
    if count == 0:
        print(f"\n  Road >= {threshold} (non-sand, non-water): 0 pixels")
        continue
    print(f"\n  Road >= {threshold} (non-sand, non-water): {count:,} pixels")
    print(f"    Albedo:    mean={albedo[road_mask].mean():.4f}  median={np.median(albedo[road_mask]):.4f}")
    print(f"    NDVI:      mean={ndvi[road_mask].mean():.4f}")
    print(f"    Building:  mean={bldg[road_mask].mean():.4f}")

# ===================================================================
# 3. COOL ROOF ANALYSIS — What do high-building areas look like?
# ===================================================================
print("\n" + "="*70)
print("3. BUILDING/ROOF SURFACE ANALYSIS (for cool roof baseline)")
print("="*70)

for threshold in [0.3, 0.5, 0.7]:
    bldg_mask = valid & (bldg >= threshold) & (sand == 0) & (water == 0)
    count = bldg_mask.sum()
    if count == 0:
        print(f"\n  Building >= {threshold} (non-sand, non-water): 0 pixels")
        continue
    print(f"\n  Building >= {threshold} (non-sand, non-water): {count:,} pixels")
    print(f"    Albedo:    mean={albedo[bldg_mask].mean():.4f}  median={np.median(albedo[bldg_mask]):.4f}")
    print(f"    NDVI:      mean={ndvi[bldg_mask].mean():.4f}")
    print(f"    Road:      mean={road[bldg_mask].mean():.4f}")
    print(f"    Height:    mean={height[bldg_mask].mean():.4f}  median={np.median(height[bldg_mask]):.4f}  max={height[bldg_mask].max():.4f}")

# ===================================================================
# 4. WATER FEATURE ANALYSIS — What do water=1 pixels look like?
# ===================================================================
print("\n" + "="*70)
print("4. WATER PIXEL ANALYSIS (water_mask=1)")
print("="*70)

water_mask = valid & (water == 1)
count = water_mask.sum()
print(f"\n  Water=1 pixels: {count:,}")
if count > 0:
    print(f"    Albedo:    mean={albedo[water_mask].mean():.4f}  median={np.median(albedo[water_mask]):.4f}  min={albedo[water_mask].min():.4f}  max={albedo[water_mask].max():.4f}")
    print(f"    NDVI:      mean={ndvi[water_mask].mean():.4f}  median={np.median(ndvi[water_mask]):.4f}  min={ndvi[water_mask].min():.4f}  max={ndvi[water_mask].max():.4f}")
    print(f"    Sand:      mean={sand[water_mask].mean():.4f}  (fraction that are also sand=1: {(sand[water_mask]==1).mean()*100:.1f}%)")
    print(f"    Building:  mean={bldg[water_mask].mean():.4f}")
    print(f"    Road:      mean={road[water_mask].mean():.4f}")
    print(f"    Height:    mean={height[water_mask].mean():.4f}")
    print(f"    Coast:     mean={coast[water_mask].mean():.1f}")

# ===================================================================
# 5. BUILDING CONSTRUCTION — What do urban built-up areas look like?
# ===================================================================
print("\n" + "="*70)
print("5. BUILT-UP AREA ANALYSIS (for construction intervention)")
print("="*70)

# Dense urban: high building + non-sand
dense_urban = valid & (bldg >= 0.3) & (sand == 0) & (water == 0)
count = dense_urban.sum()
print(f"\n  Dense urban (bldg>=0.3, sand=0, water=0): {count:,} pixels")
if count > 0:
    print(f"    ALL FEATURES:")
    print(f"    Albedo:    mean={albedo[dense_urban].mean():.4f}  median={np.median(albedo[dense_urban]):.4f}  p25={np.percentile(albedo[dense_urban],25):.4f}  p75={np.percentile(albedo[dense_urban],75):.4f}")
    print(f"    NDVI:      mean={ndvi[dense_urban].mean():.4f}  median={np.median(ndvi[dense_urban]):.4f}")
    print(f"    Building:  mean={bldg[dense_urban].mean():.4f}  median={np.median(bldg[dense_urban]):.4f}")
    print(f"    Road:      mean={road[dense_urban].mean():.4f}  median={np.median(road[dense_urban]):.4f}")
    print(f"    Height:    mean={height[dense_urban].mean():.4f}  median={np.median(height[dense_urban]):.4f}  max={height[dense_urban].max():.4f}")
    print(f"    Sand:      all 0 (by filter)")
    print(f"    Water:     all 0 (by filter)")

# ===================================================================
# 6. SAND BASELINE — What do sand=1 areas look like?
# ===================================================================
print("\n" + "="*70)
print("6. SAND BASELINE (sand=1, the pixel BEFORE interventions)")
print("="*70)

sand_mask = valid & (sand == 1)
count = sand_mask.sum()
print(f"\n  Sand=1 pixels: {count:,}")
if count > 0:
    print(f"    Albedo:    mean={albedo[sand_mask].mean():.4f}  median={np.median(albedo[sand_mask]):.4f}  p25={np.percentile(albedo[sand_mask],25):.4f}  p75={np.percentile(albedo[sand_mask],75):.4f}")
    print(f"    NDVI:      mean={ndvi[sand_mask].mean():.4f}  median={np.median(ndvi[sand_mask]):.4f}")
    print(f"    Building:  mean={bldg[sand_mask].mean():.4f}")
    print(f"    Road:      mean={road[sand_mask].mean():.4f}")
    print(f"    Height:    mean={height[sand_mask].mean():.4f}")
    print(f"    Water:     {(water[sand_mask]==1).mean()*100:.1f}% also water")
