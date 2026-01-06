import duckdb
import geopandas as gpd
import matplotlib.pyplot as plt
from shapely.wkb import loads
from shapely.errors import GEOSException

# ==========================================
# 1. CONFIGURATION
# ==========================================
min_x, min_y = 54.9, 24.9
max_x, max_y = 55.6, 25.3

print(f"🏗️ Connecting to Overture Maps (Amazon S3)...")

# ==========================================
# 2. CONNECT & QUERY
# ==========================================
try:
    con = duckdb.connect()
    con.execute("INSTALL httpfs; LOAD httpfs;")
    con.execute("INSTALL spatial; LOAD spatial;")

    # We use ST_AsWKB to request binary data
    query = f"""
        SELECT
            id,
            height,
            num_floors,
            ST_AsWKB(geometry) as geometry
        FROM read_parquet('s3://overturemaps-us-west-2/release/2025-11-19.0/theme=buildings/type=building/*')
        WHERE bbox.xmin > {min_x} 
          AND bbox.xmax < {max_x}
          AND bbox.ymin > {min_y} 
          AND bbox.ymax < {max_y}
    """

    print("   ... Executing Query (Downloading & Filtering)...")
    df = con.execute(query).fetchdf()
    print(f"✅ Download Complete! Retrieved {len(df)} building footprints.")

    # ==========================================
    # 3. ROBUST GEOMETRY PARSING
    # ==========================================
    print("   ... Parsing Geometries...")

    def safe_load(x):
        try:
            if not isinstance(x, (bytes, bytearray)):
                return None
            if len(x) == 0:
                return None
            return loads(bytes(x))
        except (GEOSException, Exception):
            return None

    # Apply the robust function
    df['geometry'] = df['geometry'].apply(safe_load)

    # Drop rows where geometry failed
    df_clean = df.dropna(subset=['geometry'])
    print(f"   ... parsing complete. Retained {len(df_clean)} of {len(df)} records.")

    # Create GeoDataFrame
    gdf = gpd.GeoDataFrame(df_clean, geometry='geometry', crs="EPSG:4326")

    # ==========================================
    # 4. COMPREHENSIVE DATA QUALITY REPORT
    # ==========================================
    if not gdf.empty:
        # Calculate statistics
        has_height = gdf[gdf['height'].notna()]
        has_floors = gdf[gdf['num_floors'].notna()]
        has_any_3d = gdf[gdf['height'].notna() | gdf['num_floors'].notna()]
        
        total = len(gdf)

        print("\n📊 DATA QUALITY REPORT:")
        print(f"   - Valid Buildings:       {total:,}")
        print(f"   - With Explicit Height:  {len(has_height):,} ({len(has_height)/total:.1%})")
        print(f"   - With Floor Count:      {len(has_floors):,} ({len(has_floors)/total:.1%})")
        print(f"   - Usable for 3D Model:   {len(has_any_3d):,} ({len(has_any_3d)/total:.1%})")
        
        # ==========================================
        # 5. VISUALIZE
        # ==========================================
        print("\n🎨 Generating Map...")
        fig, ax = plt.subplots(figsize=(12, 8))
        
        # Plot 2D Only in Light Gray
        gdf.plot(ax=ax, color='#e0e0e0', label='2D Only')
        
        # Plot 3D Candidates in Red
        if not has_any_3d.empty:
            has_any_3d.plot(ax=ax, color='#ff4444', markersize=1, label='3D Data')

        plt.title(f"Overture Maps: Buildings in Dubai\n({len(has_any_3d)} buildings with 3D data)")
        plt.legend()
        plt.axis('equal') 
        plt.show()
    else:
        print("❌ No data found in this bounding box.")

except Exception as e:
    print(f"\n❌ ERROR: {e}")