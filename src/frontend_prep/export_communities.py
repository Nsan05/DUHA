import os
import geopandas as gpd

import pandas as pd

def main():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(current_dir))
    
    input_pkl = os.path.join(project_root, "data", "final", "communities_intermediate.pkl")
    
    if not os.path.exists(input_pkl):
        print(f"ERROR: Cannot find {input_pkl}. Run compute_zonal_stats.py first.")
        return
        
    print(f"Loading intermediate data from {input_pkl}...")
    # pandas read_pickle correctly loads a GeoDataFrame
    gdf = pd.read_pickle(input_pkl)
    
    print(f"Original CRS: {gdf.crs}")
    print(f"Loaded {len(gdf)} communities with {len(gdf.columns)} attributes.")
    
    # 1. Reproject to WGS84 for Mapbox (EPSG:4326)
    wgs84_epsg = "EPSG:4326"
    print(f"Reprojecting to {wgs84_epsg} for web mapping...")
    gdf = gdf.to_crs(wgs84_epsg)
    
    # 2. Simplify geometries slightly to save payload size 
    # 0.0001 degrees is roughly 11 meters at the equator, which is plenty of precision for city-level community outlines
    print("Simplifying geometries (tolerance=0.0001)...")
    gdf['geometry'] = gdf['geometry'].simplify(tolerance=0.0001, preserve_topology=True)
    
    # 3. Fill any lingering NaNs with 0 (JSON doesn't support NaN natively)
    for c in gdf.columns:
        if c != "geometry":
            gdf[c] = gdf[c].fillna(0)
    
    # 4. Export the full GeoJSON
    out_geojson = os.path.join(project_root, "data", "final", "communities_enriched.geojson")
    print(f"Exporting full GeoJSON to {out_geojson}...")
    # remove file if it exists (fiona can sometimes complain about overwriting)
    if os.path.exists(out_geojson):
        os.remove(out_geojson)
    gdf.to_file(out_geojson, driver="GeoJSON")
    
    geo_size_mb = os.path.getsize(out_geojson) / (1024 * 1024)
    print(f"GeoJSON exported successfully. Size: {geo_size_mb:.2f} MB")
    
    # 5. Export lightweight JSON (Attributes only, no huge geometry strings)
    out_json = os.path.join(project_root, "data", "final", "community_stats.json")
    print(f"Exporting lightweight stats JSON to {out_json}...")
    
    df_no_geom = gdf.drop(columns=['geometry'])
    # Orient='records' creates a clean JSON array of objects `[{"COMM_NUM": 394, "population": 36908.0...}, ...]`
    df_no_geom.to_json(out_json, orient="records", indent=2)
    
    json_size_kb = os.path.getsize(out_json) / 1024
    print(f"JSON exported successfully. Size: {json_size_kb:.2f} KB")
    
    print("\nSUCCESS: Step 5d complete. The data is ready for the Fast API server and Next.js frontend!")

if __name__ == "__main__":
    main()
