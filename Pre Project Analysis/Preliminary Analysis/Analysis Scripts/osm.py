import osmnx as ox
import matplotlib.pyplot as plt

# ==========================================
# 1. DEFINE AREA OF INTEREST
# ==========================================
place_name = "Dubai, United Arab Emirates"

print("🗺️ Downloading Vector Data for Dubai... (This may take 2-3 mins)")

# ==========================================
# 2. DOWNLOAD LAYERS
# ==========================================

print("   ... Fetching Drive Network (Asphalt)...")
G_drive = ox.graph_from_place(place_name, network_type='drive')

print("   ... Fetching Walk Network (Pedestrian)...")
G_walk = ox.graph_from_place(place_name, network_type='walk')

print("   ... Fetching Building Footprints...")
tags = {'building': True}
gdf_buildings = ox.features_from_place(place_name, tags)

# ==========================================
# 3. QUICK INSPECTION
# ==========================================
print(f"\n✅ Download Complete!")
print(f"   - Drive Nodes: {len(G_drive.nodes)}, Edges: {len(G_drive.edges)}")
print(f"   - Walk Nodes:  {len(G_walk.nodes)},  Edges: {len(G_walk.edges)}")
print(f"   - Buildings:   {len(gdf_buildings)}")

# ==========================================
# 4. VISUALIZE 
# ==========================================
fig, ax = plt.subplots(figsize=(10, 10))

# Plot Buildings in Grey
gdf_buildings.plot(ax=ax, facecolor='gray', alpha=0.5)

# Plot Roads (Drive) in Red
ox.plot_graph(G_drive, ax=ax, node_size=0, edge_color='red', edge_linewidth=0.5, show=False)

plt.title("OSM Data: Buildings (Grey) + Roads (Red)")
plt.show()