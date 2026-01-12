import duckdb
import geopandas as gpd
import matplotlib.pyplot as plt
from shapely.wkb import loads
from shapely.errors import GEOSException

# ==========================================
# 1. CONFIGURATION
# ==========================================
# Dubai Bounding Box
min_x, min_y = 54.9, 24.8
max_x, max_y = 55.6, 25.3

# PATH TO YOUR GHSL CSV
csv_path = r"C:\Users\nithi\Desktop\Uni_Stuff\Y3\FYP\Pre Project Analysis\Preliminary Datasets\GHS_OBAT_CSV_ARE_E2020_R2024A_V1_0\GHS_OBAT_CSV_ARE_E2020_R2024A_V1_0.csv"

print(f"🏗️ Combining Overture Maps (Geometry) with GHSL (Height)...")

try:
    con = duckdb.connect()
    con.execute("INSTALL httpfs; LOAD httpfs;")
    con.execute("INSTALL spatial; LOAD spatial;")

    # ==========================================
    # 2. THE SPATIAL JOIN QUERY
    # ==========================================
    # Note: We cast columns explicitly to avoid type errors
    query = f"""
        WITH overture_buildings AS (
            SELECT 
                id, 
                height as ov_height,
                geometry
            FROM read_parquet('s3://overturemaps-us-west-2/release/2025-11-19.0/theme=buildings/type=building/*')
            WHERE bbox.xmin > {min_x} AND bbox.xmax < {max_x}
              AND bbox.ymin > {min_y} AND bbox.ymax < {max_y}
        ),
        ghsl_points AS (
            SELECT 
                CAST(lon AS DOUBLE) as lon,
                CAST(lat AS DOUBLE) as lat,
                CAST(height AS DOUBLE) as ghsl_height
            FROM read_csv('{csv_path}', auto_detect=TRUE)
            WHERE lat BETWEEN {min_y} AND {max_y}
              AND lon BETWEEN {min_x} AND {max_x}
        )
        
        SELECT 
            b.id,
            b.ov_height,
            g.ghsl_height,
            -- The Logic: Use Overture Height -> Then GHSL Height -> Then Default to 0
            COALESCE(b.ov_height, g.ghsl_height) as final_height,
            ST_AsWKB(b.geometry) as geometry
        FROM overture_buildings AS b
        LEFT JOIN ghsl_points AS g 
        ON ST_Intersects(b.geometry, ST_Point(g.lon, g.lat))
    """

    print("   ... Executing Cloud Spatial Join (This matches points to polygons)...")
    df = con.execute(query).fetchdf()
    print(f"✅ Data Retrieved! {len(df)} building records processed.")

    # ==========================================
    # 3. PARSING & CLEANING
    # ==========================================
    print("   ... Parsing Geometries...")
    
    def safe_load(x):
        try:
            if not isinstance(x, (bytes, bytearray)) or len(x) == 0: return None
            return loads(bytes(x))
        except: return None

    df['geometry'] = df['geometry'].apply(safe_load)
    gdf = gpd.GeoDataFrame(df.dropna(subset=['geometry']), geometry='geometry', crs="EPSG:4326")

    # Remove duplicates (A building might match multiple GHSL points, causing duplicate rows)
    gdf = gdf.drop_duplicates(subset='id')

    # Validation Metrics
    total = len(gdf)
    with_ov = gdf['ov_height'].notna().sum()
    with_ghsl = gdf['ghsl_height'].notna().sum()
    final_valid = gdf['final_height'].notna().sum()

    print("\n📊 DATA ENRICHMENT REPORT:")
    print(f"   - Total Buildings:      {total:,}")
    print(f"   - Overture Native Height: {with_ov:,} ({with_ov/total:.1%})")
    print(f"   - GHSL Height Contribution: {with_ghsl:,} ({with_ghsl/total:.1%})")
    print(f"   - FINAL Valid 3D Buildings: {final_valid:,} ({final_valid/total:.1%})")
    print("-" * 40)

    # ==========================================
    # 4. VISUALIZATION
    # ==========================================
    if final_valid > 0:
        print("\n🎨 Generating Map...")
        fig, ax = plt.subplots(figsize=(12, 10))
        
        # 1. Plot Base (Gray)
        gdf[gdf['final_height'].isna()].plot(ax=ax, color='#eeeeee', label='No Height')
        
        # 2. Plot 3D Data (Colored)
        gdf[gdf['final_height'].notna()].plot(
            column='final_height', 
            ax=ax, 
            cmap='plasma', 
            markersize=0.5, 
            legend=True, 
            vmax=150, # Cap color scale at 150m to see contrast better
            legend_kwds={'label': "Building Height (m)"}
        )
        
        plt.title(f"Dubai 3D Model: Overture Enriched with GHSL")
        plt.show()
    else:
        print("❌ Warning: No height data found in either source.")

except Exception as e:
    print(f"\n❌ ERROR: {e}")