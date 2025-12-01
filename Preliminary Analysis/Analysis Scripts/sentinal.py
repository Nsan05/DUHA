import rasterio
import numpy as np
import os
import glob

# ==========================================
# 1. CONFIGURATION
# ==========================================

safe_folder_path = r"C:\Users\nithi\Desktop\Uni_Stuff\Y3\FYP\Preliminary Datasets\S2A_MSIL2A_20250812T065321_N0511_R020_T40RCN_20250812T093816.SAFE\S2A_MSIL2A_20250812T065321_N0511_R020_T40RCN_20250812T093816.SAFE"

# The specific bands your project needs
required_bands = {
    'B02': 'Blue (Albedo, BSI)',
    'B03': 'Green (Albedo, NDWI)',
    'B04': 'Red (Albedo, NDVI, BSI)',
    'B08': 'NIR (Vegetation, NDVI)',
    'B11': 'SWIR (Sand/Soil Index)' 
}

# ==========================================
# 2. AUTO-FINDER FUNCTION
# ==========================================
def find_band(band_name, root_folder):
    # Recursive search for the specific band image (usually .jp2)
    search_pattern = f"*_{band_name}_*.jp2"
    for root, dirs, files in os.walk(root_folder):
        for file in files:
            if band_name in file and file.endswith(".jp2"):
                # Priority: Prefer 10m resolution if available
                if "10m" in root or "10m" in file:
                    return os.path.join(root, file)
                # Fallback: Take 20m (B11 is only available in 20m)
                return os.path.join(root, file)
    return None

# ==========================================
# 3. VALIDATION LOOP
# ==========================================
print(f"🔍 Scanning: {os.path.basename(safe_folder_path)}\n")
print(f"{'BAND':<10} {'STATUS':<10} {'RES':<10} {'DATA CHECK (Center Pixel)'}")
print("-" * 60)

all_good = True

for band, desc in required_bands.items():
    file_path = find_band(band, safe_folder_path)
    
    if file_path:
        try:
            with rasterio.open(file_path) as src:
                # Read the profile
                res = src.res[0] # Resolution (e.g. 10.0)
                
                # Read a small window in the center to check for real data
                # (Avoids reading the whole file which might be slow)
                center_x = src.width // 2
                center_y = src.height // 2
                window = rasterio.windows.Window(center_x, center_y, 10, 10)
                data = src.read(1, window=window)
                
                mean_val = np.mean(data)
                
                # Check if data is valid (not 0 or empty)
                if mean_val > 0:
                    status = "✅ OK"
                    msg = f"Mean Value: {mean_val:.0f}"
                else:
                    status = "⚠️ EMPTY"
                    msg = "Warning: Center pixels are 0 (No Data?)"
                    all_good = False
                
                print(f"{band:<10} {status:<10} {int(res)}m       {msg}")
                
        except Exception as e:
            print(f"{band:<10} ❌ ERROR    ---      Could not open file")
            all_good = False
    else:
        print(f"{band:<10} ❌ MISSING  ---      File not found in folder")
        all_good = False

print("-" * 60)
if all_good:
    print("\n🎉 SUCCESS: All required bands are present and readable.")
    print("    Note: B11 is 20m resolution. We will resize it to 10m in the next phase.")
else:
    print("\n⚠️ ISSUES FOUND: Check the errors above. You may need to re-download.")