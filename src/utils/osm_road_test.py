import osmnx as ox
import folium

OUTPUT_FILE = r"C:\Users\nithi\Desktop\Uni_Stuff\Y3\FYP\outputs\test_script_outputs\osm_road_test.html"

place_name = "Dubai, United Arab Emirates"
G = ox.graph_from_place(place_name, network_type="drive")
edges = ox.graph_to_gdfs(G, nodes=False)

edges["has_lanes"] = edges["lanes"].notna()

total_roads = len(edges)
roads_with_lanes = edges["has_lanes"].sum()

print("Total road segments:", total_roads)
print("Roads with lane data:", roads_with_lanes)

m = folium.Map(location=[25.2048, 55.2708], zoom_start=11, tiles="cartodbpositron")

folium.GeoJson(
    edges[~edges["has_lanes"]],
    style_function=lambda x: {"color": "#cccccc", "weight": 1, "opacity": 0.4}
).add_to(m)

folium.GeoJson(
    edges[edges["has_lanes"]],
    style_function=lambda x: {"color": "#0074D9", "weight": 2, "opacity": 0.8}
).add_to(m)

m.save(OUTPUT_FILE)
print(f"Map saved to {OUTPUT_FILE}")
