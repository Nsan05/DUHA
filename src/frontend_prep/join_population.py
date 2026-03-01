import geopandas as gpd
import pandas as pd
import numpy as np

def join_population_data(
    geojson_path: str = "../../data/raw/boundaries/urban_dubai_communities.geojson",
    census_path: str = "../../data/raw/census/Population_by_community.xlsx"
) -> gpd.GeoDataFrame:
    """
    Joins census population data to the urban communities GeoJSON..
    """
    print(f"Loading GeoJSON from {geojson_path}...")
    gdf = gpd.read_file(geojson_path)
    print(f"Loaded {len(gdf)} communities.")

    print(f"Loading Census data from {census_path}...")
    # Skip the first 6 rows, so row 6 (0-indexed) becomes the header
    df = pd.read_excel(census_path, header=6)
    
    # Rename columns for clarity based on known structure
    # Expected: [Code, Arabic Name, Population, Area, Density, English Name, Code]
    df = df.rename(columns={
        df.columns[0]: "community_code",
        df.columns[2]: "population",
        df.columns[3]: "area_km2",
        df.columns[4]: "pop_density",
        df.columns[5]: "cname_e_census"
    })
    
    # Ensure community_code is numeric for joining
    df['community_code'] = pd.to_numeric(df['community_code'], errors='coerce')
    
    # Drop rows where community_code is NaN (e.g. totals rows, empty rows)
    df = df.dropna(subset=['community_code'])
    df['community_code'] = df['community_code'].astype(int)
    
    # Keep only necessary columns
    df_clean = df[['community_code', 'population', 'area_km2', 'pop_density']].copy()
    
    # Double checking COMM_NUM in GeoJSON is int
    gdf['COMM_NUM'] = gdf['COMM_NUM'].astype(int)
    
    print("Joining datasets on COMM_NUM == community_code...")
    # Left join to keep all 175 urban communities
    enriched_gdf = gdf.merge(df_clean, left_on='COMM_NUM', right_on='community_code', how='left')
    
    # Check for unmatched communities
    unmatched = enriched_gdf[enriched_gdf['population'].isna()]
    if len(unmatched) > 0:
        print(f"WARNING: {len(unmatched)} communities have no population data matching their COMM_NUM.")
        print("Sample unmatched:", unmatched['CNAME_E'].head().tolist())
        
        # Fill missing values with 0 or appropriate defaults
        enriched_gdf['population'] = enriched_gdf['population'].fillna(0)
        enriched_gdf['area_km2'] = enriched_gdf['area_km2'].fillna(0)
        enriched_gdf['pop_density'] = enriched_gdf['pop_density'].fillna(0)
    else:
        print("SUCCESS: All communities matched with population data.")
    
    # Clean up duplicate code column
    if 'community_code' in enriched_gdf.columns:
        enriched_gdf = enriched_gdf.drop(columns=['community_code'])
        
    print(f"Enriched GeoDataFrame ready with {len(enriched_gdf)} rows.")
    return enriched_gdf

if __name__ == "__main__":
    import os
    # Adjust paths for direct execution from this directory
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(current_dir))
    
    geojson = os.path.join(project_root, "data", "raw", "boundaries", "urban_dubai_communities.geojson")
    census = os.path.join(project_root, "data", "raw", "census", "Population_by_community.xlsx")
    
    try:
        gdf = join_population_data(geojson, census)
        print("\nSample Output:")
        print(gdf[['COMM_NUM', 'CNAME_E', 'population', 'area_km2', 'pop_density']].head())
    except Exception as e:
        print(f"Error: {e}")
