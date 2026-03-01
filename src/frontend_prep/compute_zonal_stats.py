import os
import numpy as np
import geopandas as gpd
import rasterio
from rasterstats import zonal_stats
from join_population import join_population_data
import warnings

warnings.filterwarnings('ignore')

def compute_overall_90th_percentile(raster_path):
    with rasterio.open(raster_path) as src:
        arr = src.read(1)
        valid = arr[arr != src.nodata]
        valid = valid[~np.isnan(valid)]
        if len(valid) == 0:
            return 0
        return float(np.percentile(valid, 90))

def main():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(current_dir))
    
    geojson = os.path.join(project_root, "data", "raw", "boundaries", "urban_dubai_communities.geojson")
    census = os.path.join(project_root, "data", "raw", "census", "Population_by_community.xlsx")
    
    print("Step 5a: Joining population data...")
    gdf = join_population_data(geojson, census)
    
    morning_anomaly = os.path.join(project_root, "data", "final", "phase3a_outputs", "lst_anomaly_landsat_30m.tif")
    if not os.path.exists(morning_anomaly):
        print(f"ERROR: Cannot find {morning_anomaly}")
        return

    with rasterio.open(morning_anomaly) as src:
        raster_crs = src.crs
        
    print(f"\nReprojecting geometries from {gdf.crs} to {raster_crs}...")
    gdf = gdf.to_crs(raster_crs)
    
    # Filter out empty or null geometries that crash rasterstats
    gdf = gdf[gdf.geometry.notna()]
    gdf = gdf[~gdf.geometry.is_empty]
    
    # ---------------------------------------------
    # Define raster paths
    # ---------------------------------------------
    rasters = {
        "anomaly_morning": {
            "path": morning_anomaly,
            "stats": ['mean', 'median', 'std', 'min', 'max', 'count'],
            "extreme": True
        },
        "anomaly_afternoon": {
            "path": os.path.join(project_root, "data", "final", "phase2_outputs", "lst_anomaly_30m.tif"),
            "stats": ['mean', 'median', 'std', 'min', 'max', 'count'],
            "extreme": True
        },
        "anomaly_night": {
            "path": os.path.join(project_root, "data", "final", "phase3b_outputs", "lst_anomaly_nighttime_30m.tif"),
            "stats": ['mean', 'median', 'std', 'min', 'max', 'count'],
            "extreme": True
        },
        "diurnal_range": {
            "path": os.path.join(project_root, "data", "final", "phase3c_outputs", "diurnal_range_30m.tif"),
            "stats": ['mean', 'std'],
            "extreme": False
        },
        "ndvi": {
            "path": os.path.join(project_root, "data", "final", "phase1_features", "ndvi_30m.tif"),
            "stats": ['mean'],
            "extreme": False
        },
        "albedo": {
            "path": os.path.join(project_root, "data", "final", "phase1_features", "albedo_30m.tif"),
            "stats": ['mean'],
            "extreme": False
        },
        "building_density": {
            "path": os.path.join(project_root, "data", "final", "phase1_features", "building_density_30m.tif"),
            "stats": ['mean'],
            "extreme": False
        },
        "building_height": {
            "path": os.path.join(project_root, "data", "final", "phase1_features", "height_30m.tif"),
            "stats": ['mean'],
            "extreme": False
        },
        "road_density": {
            "path": os.path.join(project_root, "data", "final", "phase1_features", "road_density_30m.tif"),
            "stats": ['mean'],
            "extreme": False
        },
        "sand_fraction": {
            "path": os.path.join(project_root, "data", "final", "phase1_features", "sand_mask_30m.tif"),
            "stats": ['mean'],
            "extreme": False
        },
        "water_fraction": {
            "path": os.path.join(project_root, "data", "final", "phase1_features", "water_mask_full_30m.tif"),
            "stats": ['mean'],
            "extreme": False
        },
        "dist_to_coast": {
            "path": os.path.join(project_root, "data", "final", "phase1_features", "dist_to_coast_30m.tif"),
            "stats": ['mean'],
            "extreme": False
        }
    }
    
    extreme_thresholds = {}
    print("\n--- Calculating 90th Percentiles for Extreme Heat Thresholds ---")
    for key, info in rasters.items():
        if info["extreme"]:
            ext_score = compute_overall_90th_percentile(info["path"])
            extreme_thresholds[key] = ext_score
            print(f"90th percentile for {key}: {ext_score:.2f} K")
            
    # Custom Zonal Functions
    # get % of pixels in community above threshold
    def get_add_stats_func(threshold):
        def extreme_pct_func(masked):
            valid = masked[~masked.mask] # keep valid pixels
            valid = valid[~np.isnan(valid)] # remove nan values
            if len(valid) == 0:
                return 0.0
            return float((valid > threshold).sum()) / len(valid)
        return {'extreme_pct': extreme_pct_func}
        
    # get % of pixels in community with NDVI > 0.2
    def get_green_frac_func():
        def green_fraction_func(masked):
            valid = masked[~masked.mask]
            valid = valid[~np.isnan(valid)]
            if len(valid) == 0:
                return 0.0
            return float((valid > 0.2).sum()) / len(valid)
        return {'green_fraction': green_fraction_func}

    print("\n--- Computing Zonal Stats per Community ---")
    for key, info in rasters.items():
        print(f"[{key}] Processing...")
        path = info["path"]
        
        if not os.path.exists(path):
            print(f"ERROR: File not found: {path}. Skipping.")
            continue
            
        add_stats = None
        if info["extreme"]:
            add_stats = get_add_stats_func(extreme_thresholds[key])
        elif key == "ndvi":
            add_stats = get_green_frac_func()
            
        with rasterio.open(path) as src:
            nodata_val = src.nodata
            
        stats = zonal_stats(
            gdf, 
            path, 
            stats=info["stats"], 
            add_stats=add_stats,
            nodata=nodata_val
        )
        
        # Adding all the stat data to the gdf
        for stat_name in info["stats"]:
            col_name = f"{key}_{stat_name}"
            gdf[col_name] = [s[stat_name] for s in stats]
            
        if info["extreme"]:
            gdf[f"{key}_extreme_pct"] = [s.get('extreme_pct', 0.0) for s in stats]
        elif key == "ndvi":
            gdf["green_fraction"] = [s.get('green_fraction', 0.0) for s in stats]
            
    # Round off float columns to save space
    for c in gdf.columns:
        if c != "geometry" and gdf[c].dtype.kind in 'fc':
            gdf[c] = gdf[c].astype(float).round(4)
                
    # Generate green_mask_30m.tif
    ndvi_path = rasters["ndvi"]["path"]
    green_mask_path = os.path.join(project_root, "data", "final", "phase1_features", "green_mask_30m.tif")
    if os.path.exists(ndvi_path):
        print("\n--- Generating green_mask_30m.tif (Step 5c) ---")
        with rasterio.open(ndvi_path) as src:
            meta = src.meta.copy()
            arr = src.read(1)
            nodata = meta.get('nodata', -9999)
            if nodata is None: nodata = -9999
            
            green = np.where(arr > 0.2, 1, 0).astype(meta['dtype'])
            green[arr == src.nodata] = nodata
            meta.update(nodata=nodata)
            
            with rasterio.open(green_mask_path, "w", **meta) as dst:
                dst.write(green, 1)
        print("Done.")

    # Save to an intermediate pickle so Step 5d can just load it and export
    output_intermediate = os.path.join(project_root, "data", "final", "communities_intermediate.pkl")
    gdf.to_pickle(output_intermediate)
    
    print(f"\nSUCCESS: Processing complete. Intermediate results saved to {output_intermediate}")
    
    # Just to verify, printing sample
    sample_cols = ['COMM_NUM', 'anomaly_afternoon_mean', 'anomaly_afternoon_extreme_pct', 'ndvi_mean', 'green_fraction']
    print("\nSample Data:")
    print(gdf[sample_cols].head().to_string())

if __name__ == "__main__":
    main()
