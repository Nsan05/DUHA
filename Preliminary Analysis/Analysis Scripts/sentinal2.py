import rasterio
import numpy as np
import matplotlib.pyplot as plt
import os

# ==========================================
# 1. CONFIGURATION
# ==========================================
# PASTE YOUR SAME SAFE FOLDER PATH HERE
safe_folder_path = r"C:\Users\nithi\Desktop\Uni_Stuff\Y3\FYP\Preliminary Datasets\S2A_MSIL2A_20250812T065321_N0511_R020_T40RCN_20250812T093816.SAFE\S2A_MSIL2A_20250812T065321_N0511_R020_T40RCN_20250812T093816.SAFE"

# ==========================================
# 2. HELPER FUNCTION (Same as before)
# ==========================================
def find_band(band_name, root_folder):
    for root, dirs, files in os.walk(root_folder):
        for file in files:
            if band_name in file and file.endswith(".jp2"):
                if "10m" in root or "10m" in file:
                    return os.path.join(root, file)
                return os.path.join(root, file)
    return None

# ==========================================
# 3. GENERATE MAP
# ==========================================
print("🎨 Loading bands to generate RGB map...")

try:
    # Find the RGB bands
    path_r = find_band('B04', safe_folder_path) # Red
    path_g = find_band('B03', safe_folder_path) # Green
    path_b = find_band('B02', safe_folder_path) # Blue

    if not (path_r and path_g and path_b):
        raise FileNotFoundError("Could not find one or more RGB bands (B04, B03, B02).")

    # Open and read them (We read 100% of the image this time)
    # Note: This might take 5-10 seconds as these are large files
    with rasterio.open(path_r) as src:
        red = src.read(1).astype(float)
        profile = src.profile # Save metadata for plotting
        
    with rasterio.open(path_g) as src:
        green = src.read(1).astype(float)
        
    with rasterio.open(path_b) as src:
        blue = src.read(1).astype(float)

    # ==========================================
    # 4. NORMALIZE FOR DISPLAY
    # ==========================================
    # Sentinel-2 data is 0-10000 (Reflectance). 
    # Computer screens need 0-1 (Float) or 0-255 (Byte).
    # A scale factor of 3000 is usually good for brightness.
    scale_factor = 3000
    
    # Stack into an RGB array
    rgb = np.dstack((red, green, blue))
    
    # Clip values to max brightness (avoid whiteout) and normalize to 0-1
    rgb = np.clip(rgb / scale_factor, 0, 1)

    # ==========================================
    # 5. PLOT
    # ==========================================
    plt.figure(figsize=(12, 12))
    plt.imshow(rgb)
    plt.title(f"Sentinel-2 True Color View\n{os.path.basename(safe_folder_path)}")
    plt.xlabel("Column Pixel")
    plt.ylabel("Row Pixel")
    plt.show()
    
    print("✅ Map Generated. Check the window above.")
    print("   - If it looks like a photo of Dubai, you are good.")
    print("   - If it looks black, increase the scale_factor.")
    print("   - If it looks white, decrease the scale_factor.")

except Exception as e:
    print(f"❌ Error: {e}")