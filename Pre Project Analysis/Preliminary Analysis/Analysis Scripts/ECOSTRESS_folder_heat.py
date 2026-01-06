import h5py
import numpy as np
import matplotlib.pyplot as plt
import os
import glob

# ==========================================
# 1. SETUP: PASTE YOUR FOLDER PATH HERE
# ==========================================
# Example: r"C:\Users\nithi\Desktop\FYP\Datasets\ECOSTRESS"
folder_path = r"C:\Users\nithi\Desktop\Uni_Stuff\Y3\FYP\Datasets\Preliminary Analysis\ECO_L2_LSTE_Morning"
# ==========================================
# 2. PROCESSING LOOP
# ==========================================
def process_folder(path):
    # Find all .h5 files in the folder
    file_list = glob.glob(os.path.join(path, "*.h5"))
    
    print(f"📂 Found {len(file_list)} files. Processing now...\n")

    for i, filepath in enumerate(file_list):
        filename = os.path.basename(filepath)
        print(f"[{i+1}/{len(file_list)}] Processing: {filename}...")

        try:
            with h5py.File(filepath, 'r') as f:
                # --- A. Check File Structure ---
                # ECOSTRESS usually keeps data in 'SDS' group
                if 'SDS' not in f.keys():
                    print(f"   ⚠️ SKIPPING: 'SDS' group not found. (Might be a Geo file?)")
                    continue
                
                if 'LST' not in f['SDS'].keys():
                    print(f"   ⚠️ SKIPPING: 'LST' dataset not found.")
                    continue

                # --- B. Extract Raw Data ---
                lst_raw = f['SDS']['LST'][:]

                # --- C. Convert to Celsius ---
                # Formula: (DN * 0.02) - 273.15
                # Convert to float first to handle NaNs
                lst_celsius = lst_raw.astype(float)
                lst_celsius = (lst_celsius * 0.02) - 273.15

                # --- D. Clean the Data (Masking) ---
                # 0 in raw data = -273.15 C (Space/Fill) -> Mask it
                # > 100 C is usually an error flag -> Mask it
                # We mask < 10°C to hide deep space/errors (Dubai is never 10C in summer)
                lst_celsius[lst_celsius < 10] = np.nan 
                lst_celsius[lst_celsius > 80] = np.nan

                # --- E. Calculate Stats ---
                # Use nanmin/nanmax to ignore the masked values
                min_temp = np.nanmin(lst_celsius)
                max_temp = np.nanmax(lst_celsius)
                mean_temp = np.nanmean(lst_celsius)

                # --- F. Plotting ---
                plt.figure(figsize=(10, 6))
                
                # Use 'jet' so Blue = Cool (Water) and Red = Hot (Land)
                # vmin/vmax locks the scale so images are comparable
                img = plt.imshow(lst_celsius, cmap='jet', vmin=10, vmax=70)
                
                cbar = plt.colorbar(img)
                cbar.set_label('Surface Temperature (°C)', rotation=270, labelpad=15)
                
                plt.title(f"File: {filename}\nMin: {min_temp:.1f}°C | Max: {max_temp:.1f}°C | Mean: {mean_temp:.1f}°C")
                plt.axis('off') # Hides the pixel coordinates
                plt.tight_layout()
                plt.show()

        except Exception as e:
            print(f"   ❌ ERROR: Could not process file. Reason: {e}")

# ==========================================
# 3. RUN IT
# ==========================================
process_folder(folder_path)