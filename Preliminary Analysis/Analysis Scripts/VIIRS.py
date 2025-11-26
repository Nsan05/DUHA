import netCDF4 as nc
import numpy as np
import matplotlib.pyplot as plt

# ==========================================
# 1. Paths
# ==========================================
filepath = r"C:\Users\nithi\Desktop\Uni_Stuff\Y3\FYP\Datasets\Preliminary Analysis\VIIRS VNP21\VNP21.A2025224.2206.002.2025227232908.nc"

try:
    print(f"--- Opening: {filepath.split('\\')[-1]} ---")
    ds = nc.Dataset(filepath)
    
    main_group = ds.groups['VIIRS_Swath_LSTE']
    geo_group = main_group.groups['Geolocation Fields']
    data_group = main_group.groups['Data Fields']

    # ==========================================
    # 2. EXTRACT & CONVERT
    # ==========================================
    lat = geo_group.variables['latitude'][:]
    lon = geo_group.variables['longitude'][:]
    
    # Load data (auto-converts to Kelvin)
    lst_kelvin = data_group.variables['LST'][:]
    
    # Fill masked values with NaN
    if np.ma.is_masked(lst_kelvin):
        lst_kelvin = lst_kelvin.filled(np.nan)

    # Convert to Celsius
    lst_celsius = lst_kelvin - 273.15

    # ==========================================
    # 3. DEFINE WIDER AREA
    # ==========================================
    mask = (lon > 51.0) & (lon < 57.0) & (lat > 22.0) & (lat < 27.0)

    if np.sum(mask) > 0:
        plt.figure(figsize=(12, 10)) # Made figure slightly larger for wider view
        
        # Plotting
        scatter = plt.scatter(lon[mask], lat[mask], c=lst_celsius[mask], cmap='jet', s=1, vmin=25, vmax=55)
        
        plt.colorbar(scatter, label="Temperature (°C)")
        plt.title(f"VIIRS LST - Full Swath View\n(Max Temp: {np.nanmax(lst_celsius[mask]):.1f}°C)")
        plt.xlabel("Longitude")
        plt.ylabel("Latitude")
        plt.grid(True, alpha=0.3)
        
        # Make axes equal so the map isn't stretched
        plt.axis('equal') 
        
        plt.show()
        
        print(f"Min Temp found: {np.nanmin(lst_celsius[mask]):.1f}°C")
        print(f"Max Temp found: {np.nanmax(lst_celsius[mask]):.1f}°C")
    else:
        print("⚠️ Data loaded, but no valid pixels found.")

except Exception as e:
    print(f"❌ Failed: {e}")
    import traceback
    traceback.print_exc()