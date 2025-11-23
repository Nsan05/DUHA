import h5py
import numpy as np
import matplotlib.pyplot as plt

# 1. PATHS TO BOTH FILES (Update these!)
lst_file = r"C:\Users\nithi\Desktop\Uni_Stuff\Y3\FYP\Datasets\Preliminary Analysis\ECO_L2_LSTE_Morning\ECOv002_L2_LSTE_40400_016_20250821T075945_0713_01.h5"
geo_file = r"C:\Users\nithi\Desktop\Uni_Stuff\Y3\FYP\Datasets\Preliminary Analysis\ECO_L2_LSTE_Morning\ECOv002_L1B_GEO_40400_016_20250821T075945_0713_01.h5"

try:
    # 2. READ TEMPERATURE (From File A)
    with h5py.File(lst_file, 'r') as f_lst:
        lst_raw = f_lst['SDS']['LST'][:]
        lst_celsius = (lst_raw.astype(float) * 0.02) - 273.15
        
        # Clean errors
        lst_celsius[lst_celsius < 10] = np.nan
        lst_celsius[lst_celsius > 70] = np.nan

    # 3. READ COORDINATES (From File B)
    with h5py.File(geo_file, 'r') as f_geo:
        # Geolocation is usually under 'Geolocation' group
        lat = f_geo['Geolocation']['latitude'][:]
        lon = f_geo['Geolocation']['longitude'][:]

    # 4. PLOT THE UN-ROTATED MAP
    plt.figure(figsize=(10, 8))
    
    # Use scatter to map pixels to their real Lat/Lon
    plt.scatter(lon, lat, c=lst_celsius, cmap='jet', s=0.15, vmin=5, vmax=70)
    
    plt.colorbar(label="Temperature (°C)")
    plt.xlabel("Longitude")
    plt.ylabel("Latitude")
    plt.title("Correctly Georeferenced Dubai Heat Map")
    plt.grid(True, alpha=0.3)
    plt.gca().set_facecolor('lightgray')
    plt.show()
    
    print("✅ Success: Map is now un-rotated.")

except Exception as e:
    print(f"❌ Error: {e}\n(Did you download the GEO file?)")