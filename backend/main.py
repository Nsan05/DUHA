import os
import json
import numpy as np
import pandas as pd
from typing import List, Dict, Any, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import rasterio
from pyproj import Transformer
import joblib
import shap
from shapely.geometry import shape
from shapely.ops import transform as shapely_transform
import rasterio.mask
from fastapi.responses import Response

try:
    from rio_tiler.io import Reader
    from rio_tiler.colormap import cmap
    from rio_tiler.profiles import img_profiles
except ImportError:
    Reader = None
    cmap = None


# --- CONFIGURATION & PATHS ---
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
DATA_DIR = os.path.join(PROJECT_ROOT, "data")

COMMUNITIES_JSON_PATH = os.path.join(DATA_DIR, "final", "community_stats.json")
COMMUNITIES_GEOJSON_PATH = os.path.join(DATA_DIR, "final", "communities_enriched.geojson")

MODEL_PATHS = {
    "morning": os.path.join(DATA_DIR, "models", "gb_model_landsat.joblib"),
    "afternoon": os.path.join(DATA_DIR, "models", "gb_model_anomaly.joblib"),
    "night": os.path.join(DATA_DIR, "models", "gb_model_nighttime.joblib")
}

RASTER_PATHS = {
    "features": {
        "ndvi_mean": os.path.join(DATA_DIR, "final", "phase1_features", "ndvi_30m.tif"),
        "albedo_mean": os.path.join(DATA_DIR, "final", "phase1_features", "albedo_30m.tif"),
        "building_density_mean": os.path.join(DATA_DIR, "final", "phase1_features", "building_density_30m.tif"),
        "height_mean": os.path.join(DATA_DIR, "final", "phase1_features", "height_30m.tif"),
        "road_density_mean": os.path.join(DATA_DIR, "final", "phase1_features", "road_density_30m.tif"),
        "sand_mask_fraction": os.path.join(DATA_DIR, "final", "phase1_features", "sand_mask_30m.tif"),
        "water_mask_full_fraction": os.path.join(DATA_DIR, "final", "phase1_features", "water_mask_full_30m.tif"),
        "dist_to_coast_m": os.path.join(DATA_DIR, "final", "phase1_features", "dist_to_coast_30m.tif")
    },
    "anomalies": {
        "morning": os.path.join(DATA_DIR, "final", "phase3a_outputs", "lst_anomaly_landsat_30m.tif"),
        "afternoon": os.path.join(DATA_DIR, "final", "phase2_outputs", "lst_anomaly_30m.tif"),
        "night": os.path.join(DATA_DIR, "final", "phase3b_outputs", "lst_anomaly_nighttime_30m.tif")
    }
}

# Ensure features list order accurately matches the model training exactly
FEATURE_ORDER = [
    'ndvi_mean', 'albedo_mean', 'building_density_mean', 'height_mean',
    'road_density_mean', 'sand_mask_fraction', 'water_mask_full_fraction', 'dist_to_coast_m'
]

# --- GLOBAL APP STATE ---
class AppState:
    communities_geojson: dict = {}
    communities_stats: list = []
    models: dict = {}
    explainers: dict = {}
    raster_handles: dict = {"features": {}, "anomalies": {}}
    transformer: Transformer = None

state = AppState()

# --- LIFESPAN MANAGER --- Runs when server starts
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Starting up Dubai Urban Heat API...")
    
    # 1. Load Community GeoJSON Data for the map drawing response
    with open(COMMUNITIES_GEOJSON_PATH, "r", encoding="utf-8") as f:
        state.communities_geojson = json.load(f)
        
    # 2. Load ML Models
    for time_of_day, path in MODEL_PATHS.items():
        if os.path.exists(path):
            state.models[time_of_day] = joblib.load(path)
            try:
                # TreeExplainer is ideal for HistGradientBoosting
                state.explainers[time_of_day] = shap.TreeExplainer(state.models[time_of_day])
            except Exception as e:
                print(f"Failed to initialize SHAP for {time_of_day}: {e}. Creating generic explainer fallback.")
                state.explainers[time_of_day] = shap.Explainer(state.models[time_of_day].predict, np.zeros((1, 8)))
        else:
            print(f"Warning: Model not found at {path}")
            
    # 3. Open Raster Handles
    for category in ["features", "anomalies"]:
        for key, path in RASTER_PATHS[category].items():
            if os.path.exists(path):
                state.raster_handles[category][key] = rasterio.open(path)
            else:
                print(f"Warning: Raster not found at {path}")

    # Set up coordinate transformer assuming all rasters are EPSG:32640 (UTM Zone 40N)
    state.transformer = Transformer.from_crs("EPSG:4326", "EPSG:32640", always_xy=True)
    
    yield # Ready to serve traffic!
    
    print("Shutting down... Closing raster handles.")
    for category in ["features", "anomalies"]:
        for handle in state.raster_handles[category].values():
            handle.close()

# --- FASTAPI APP ---
app = FastAPI(title="Dubai Urban Heat API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- REQUEST MODELS ---
class CoordinateRequest(BaseModel):
    lat: float
    lon: float
    time_of_day: str = "afternoon" # 'morning', 'afternoon', or 'night'

class PredictionRequest(BaseModel):
    features: Dict[str, float]

class PredictionBatchRequest(BaseModel):
    pixels: List[Dict[str, float]]

# --- UTILS ---
def sample_rasters(lon: float, lat: float) -> tuple[Dict[str, float], Dict[str, float]]:
    """Samples all rasters at a given coordinate. Throws HTTP 400 if out of bounds/NaN."""
    x, y = state.transformer.transform(lon, lat)
    
    features = {}
    anomalies = {}
    
    # Check if rasters were loaded corrrectly  
    handle = state.raster_handles["features"].get("building_density_mean")
    if not handle:
        raise HTTPException(status_code=500, detail="Urban boundary mask (building density) not loaded.")
        
    try:
        val = list(handle.sample([(x, y)]))[0][0]
        if np.isnan(val) or val == handle.nodata:
            raise HTTPException(status_code=400, detail="Out of Bounds. Please click within the valid urban Dubai communities.")
    except IndexError:
        raise HTTPException(status_code=400, detail="Out of Bounds. Please click within the valid urban Dubai communities.")
        
    # Valid pixel - sample everything
    for key, handle in state.raster_handles["features"].items():
        val = list(handle.sample([(x, y)]))[0][0]
        features[key] = float(val) if not np.isnan(val) else 0.0
        
    for key, handle in state.raster_handles["anomalies"].items():
        val = list(handle.sample([(x, y)]))[0][0]
        anomalies[key] = float(val) if not np.isnan(val) else 0.0
        
    return features, anomalies

# --- ENDPOINTS ---
@app.get("/api/communities")
async def get_communities():
    """Returns the full enriched GeoJSON for Mapbox to draw the map layers + global feature ranges."""
    
    # Calculate global min/max ranges for the frontend radar chart
    ranges = {
        "ndvi_mean": [float("inf"), float("-inf")],
        "albedo_mean": [float("inf"), float("-inf")],
        "building_density_mean": [float("inf"), float("-inf")],
        "height_mean": [float("inf"), float("-inf")],
        "road_density_mean": [float("inf"), float("-inf")],
        "sand_fraction_mean": [float("inf"), float("-inf")], 
        "water_fraction_mean": [float("inf"), float("-inf")],
        "dist_to_coast_mean": [float("inf"), float("-inf")],
    }
    
    for f in state.communities_geojson.get("features", []):
        props = f.get("properties", {})
        for key in ranges.keys():
            val = props.get(key) # get the actual values from the geojson file
            if val is not None:
                if val < ranges[key][0]: ranges[key][0] = val
                if val > ranges[key][1]: ranges[key][1] = val
                
    # Fallback to defaults if any were untouched
    for k, v in ranges.items():
        if v[0] == float("inf"): v[0] = 0
        if v[1] == float("-inf"): v[1] = 1

    return {
        **state.communities_geojson,
        "global_feature_ranges": ranges
    }

@app.post("/api/pixel")
async def get_pixel_data(req: CoordinateRequest):
    """Samples all rasters at the clicked location and returns features and raw anomalies."""
    features, anomalies = sample_rasters(req.lon, req.lat)
    return {
        "features": features,
        "anomalies": anomalies 
    }

@app.post("/api/predict")
async def predict_anomaly(req: PredictionRequest):
    """Runs a feature override vector through all 3 ML models and returns new anomalies."""
    feature_dict = req.features
    
    try:
        ordered_data = [feature_dict[f] for f in FEATURE_ORDER]
    except KeyError as e:
        raise HTTPException(status_code=400, detail=f"Missing feature in request: {e}")
        
    predictions = {}
    for time_of_day, model in state.models.items():
        try:
            # Sklearn expects exact column names from training. 
            order = list(FEATURE_ORDER)
            if time_of_day == "night":
                order[-1] = 'dist_to_coast_mean'
                
            X = pd.DataFrame([ordered_data], columns=order)
            
            val = model.predict(X)[0]
            predictions[time_of_day] = float(val)
        except Exception as e:
            print(f"Prediction failed for {time_of_day}: {e}")
            predictions[time_of_day] = None
            
    return {"predicted_anomalies": predictions}

@app.post("/api/predict-batch")
async def predict_batch(req: PredictionBatchRequest):
    """Runs a batch of feature override vectors through all 3 ML models and returns average new anomalies."""
    # If no pixels, return 
    if not req.pixels:
        raise HTTPException(status_code=400, detail="Empty pixels array")
        
    predictions_sum = {"morning": 0.0, "afternoon": 0.0, "night": 0.0}
    valid_counts = {"morning": 0, "afternoon": 0, "night": 0}
    
    # We can optimize by compiling all rows into a single pandas DataFrame
    ordered_rows = []
    for feature_dict in req.pixels:
        try:
            ordered_rows.append([feature_dict[f] for f in FEATURE_ORDER]) # Added the values of each each of each pixel into one row
        except KeyError as e:
            raise HTTPException(status_code=400, detail=f"Missing feature in request: {e}")
            
    # contains the average predictions for all the times of day
    avg_predictions = {}
    for time_of_day, model in state.models.items():
        try:
            order = list(FEATURE_ORDER)
            if time_of_day == "night":
                order[-1] = 'dist_to_coast_mean'
                
            X = pd.DataFrame(ordered_rows, columns=order)
            
            # Predict in bulk
            vals = model.predict(X)
            # get sum of predictions and total num
            predictions_sum[time_of_day] = float(np.sum(vals))
            valid_counts[time_of_day] = len(vals)
        except Exception as e:
            print(f"Batch prediction failed for {time_of_day}: {e}")
            
    for tod in ["morning", "afternoon", "night"]:
        if valid_counts[tod] > 0:
            avg_predictions[tod] = predictions_sum[tod] / valid_counts[tod]
        else:
            avg_predictions[tod] = None
            
    return {"predicted_anomalies": avg_predictions}

@app.post("/api/shap")
async def get_shap_explanation(req: CoordinateRequest):
    """Extracts SHAP values for a given coordinate to explain why the pixel is hot/cold."""
    # 1. Sample literal features at the location
    features, anomalies = sample_rasters(req.lon, req.lat)
    
    # 2. Get the requested ML model + explainer
    model_key = req.time_of_day
    explainer = state.explainers.get(model_key)
    if not explainer:
        raise HTTPException(status_code=500, detail=f"Explainer AI engine not loaded for {model_key}")
        
    order = list(FEATURE_ORDER)
    if model_key == "night":
        order[-1] = 'dist_to_coast_mean'
        
    X = pd.DataFrame([[features[f] for f in FEATURE_ORDER]], columns=order)
    
    # 3. Calculate SHAP
    shap_vals = explainer(X)
    
    try:
        values = shap_vals.values[0]
    except Exception:
        raise HTTPException(status_code=500, detail="Error formatting SHAP explanation vector.")

    contributions = {feat: float(val) for feat, val in zip(FEATURE_ORDER, values)}
    
    # 4. Generate the Plain-Language sentence
    # Sort contributions by absolute magnitude to find top drivers
    sorted_drivers = sorted(contributions.items(), key=lambda item: abs(item[1]), reverse=True)
    
    # Clean up feature names for reading
    friendly_names = {
        "ndvi_mean": "vegetation cover",
        "albedo_mean": "surface reflectivity",
        "building_density_mean": "building density",
        "height_mean": "building height",
        "road_density_mean": "asphalt streets",
        "sand_mask_fraction": "open sand",
        "water_mask_full_fraction": "water bodies",
        "dist_to_coast_m": "distance from the coast",
        "dist_to_coast_mean": "distance from the coast" 
    }
    
    anomaly = anomalies.get(model_key, 0.0)
    adjective = "warmer" if anomaly > 0 else "cooler"
    
    sentence = f"This location is {abs(anomaly):.1f}°C {adjective} than the city average. "
    
    # Units for displaying raw feature values
    friendly_units = {
        "ndvi_mean": "",
        "albedo_mean": "",
        "building_density_mean": "",
        "height_mean": "m",
        "road_density_mean": "",
        "sand_mask_fraction": "",
        "water_mask_full_fraction": "",
        "dist_to_coast_m": "m",
        "dist_to_coast_mean": "m"
    }
    
    # Grab the top 4 drivers
    top_4 = sorted_drivers[:4]
    
    sentence += "The primary factors driving this temperature are: "
    drivers_text = []
    
    for feat, val in top_4:
        name = friendly_names.get(feat, feat)
        effect = "heating" if val > 0 else "cooling"
        # Include the raw feature value so the user understands what the pixel actually looks like
        raw_val = features.get(feat, features.get("dist_to_coast_m", 0.0))
        unit = friendly_units.get(feat, "")
        drivers_text.append(f"{name} = {raw_val:.2f}{unit} ({effect} by {abs(val):.2f}°C)")
        
    sentence += ", ".join(drivers_text) + ". "
    
    sentence += "(Note: These values are SHAP contributions. They represent exactly how many degrees Celsius each specific feature added or subtracted from the city's baseline temperature at this specific pixel, according to the AI model)."
    
    return {
        "shap_values": contributions,
        "explanation": sentence,
        "base_value": float(shap_vals.base_values[0]) if hasattr(shap_vals, 'base_values') else 0.0
    }

@app.get("/api/community/{comm_num}/pixels")
async def get_community_pixels(comm_num: int, time: str = "afternoon"): # default time is afternoon
    """
    Returns a GeoJSON FeatureCollection of 30x30m pixels covering the specified community.
    Each feature has the temperature anomaly for the requested time of day.
    """
    if time not in ["morning", "afternoon", "night"]:
        raise HTTPException(status_code=400, detail="Invalid time of day")
        
    # 1. Find the community polygon features that matches the comm_num
    feature = next((f for f in state.communities_geojson.get("features", []) if f["properties"].get("COMM_NUM") == comm_num), None)
    if not feature:
        raise HTTPException(status_code=404, detail=f"Community {comm_num} not found")
        
    # 4326 - lat/lon    
    geom_4326 = shape(feature["geometry"])
    
    # 2. Project to native CRS (EPSG:32640, matching the raster)
    geom_32640 = shapely_transform(state.transformer.transform, geom_4326)
    
    # 3. Mask the anomaly raster using the projected geometry
    # Getting the anomaly raster
    handle = state.raster_handles["anomalies"].get(time)
    if not handle:
        raise HTTPException(status_code=500, detail=f"Raster for {time} not loaded")
        
    # crop=True extracts just the bounding box of the polygon
    # out_image: pixel values
    # out_transform: affine transform
    try:
        out_image, out_transform = rasterio.mask.mask(handle, [geom_32640], crop=True, filled=False)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error masking raster: {str(e)}")
        
    pixels = []
    stats = {"count": 0, "min": float('inf'), "max": float('-inf'), "sum": 0.0}
    
    # out_image usually has shape (1, height, width)
    data = out_image[0]
    
    # transformer for going back to EPSG:4326
    # Note: setting always_xy to True avoids lat/lon vs lon/lat order issues
    transformer_back = Transformer.from_crs("EPSG:32640", "EPSG:4326", always_xy=True)
    
    # Pixel dimensions
    pixel_width = out_transform.a
    pixel_height = out_transform.e
    
    # Determine valid pixels - creating a mask for pixels that are not nodata
    if hasattr(data, 'mask'):
        valid_mask = ~data.mask
    else:
        valid_mask = data != handle.nodata
        
    rows, cols = np.where(valid_mask)
    
    # Optimization: Instead of building full dict per loop step, build efficiently
    lons_t, lats_t = [], []
    for r, c in zip(rows, cols):
        # Top left corner of pixel
        x_tl, y_tl = out_transform * (c, r)
        
        # Add all 5 corners of pixel to lists
        lons_t.extend([x_tl, x_tl + pixel_width, x_tl + pixel_width, x_tl, x_tl])
        lats_t.extend([y_tl, y_tl, y_tl + pixel_height, y_tl + pixel_height, y_tl])
        
    # Batch transform all corners
    if lons_t and lats_t:
        lons_4326, lats_4326 = transformer_back.transform(lons_t, lats_t)
    else:
        lons_4326, lats_4326 = [], []

    idx = 0
    for r, c in zip(rows, cols):
        val = float(data[r, c])
        
        # Update stats
        stats["count"] += 1
        stats["sum"] += val
        if val < stats["min"]: stats["min"] = val
        if val > stats["max"]: stats["max"] = val
        
        # Extract the 5 processed corners for this pixel
        corners_4326 = [
            (lons_4326[idx], lats_4326[idx]),
            (lons_4326[idx+1], lats_4326[idx+1]),
            (lons_4326[idx+2], lats_4326[idx+2]),
            (lons_4326[idx+3], lats_4326[idx+3]),
            (lons_4326[idx+4], lats_4326[idx+4])
        ]
        idx += 5
        
        pixels.append({
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [corners_4326]
            },
            "properties": {
                "anomaly": float(f"{val:.3f}"), # Round to 3 decimal places to reduce JSON size
                "row": int(r),
                "col": int(c)
            }
        })
        
    if stats["count"] > 0:
        stats["mean"] = stats["sum"] / stats["count"]
    else:
        stats["min"] = stats["max"] = stats["mean"] = 0.0

    return {
        "grid": {
            "type": "FeatureCollection",
            "features": pixels
        },
        "stats": stats
    }

@app.get("/api/tiles/{layer}/{z}/{x}/{y}.png")
async def get_tile(
    layer: str, 
    z: int, x: int, y: int,  # Zoom level (z), tile column (x), tile row (y)
    colormap: str = "viridis", 
    min_val: float = 0.0, # Only default values to use when frontend does not send the values
    max_val: float = 1.0, # Only default values to use when frontend does not send the values
    nodata: float = None
):
    """
    Serves XYZ web mercator tiles for raster overlays dynamically using rio-tiler.
    """
    if Reader is None:
        raise HTTPException(status_code=500, detail="rio-tiler is not installed")
        
    # Check if the layer exists in RASTER_PATHS
    path = RASTER_PATHS["features"].get(layer) or RASTER_PATHS["anomalies"].get(layer)
    if not path or not os.path.exists(path):
        raise HTTPException(status_code=404, detail=f"Layer '{layer}' not found or file missing")
        
    try:
        with Reader(path) as src:
            # We configure nodata directly if requested, else rely on the tiff's internal nodata
            if nodata is not None:
                src.nodata = nodata

            # Read the tile from the source raster
            img = src.tile(x, y, z)
            
            # Rescale the raw data to 0-255 based on min/max - for the map colour projection
            img.rescale(in_range=((min_val, max_val),))
            
            # Apply the requested matplotlib colormap
            # Special check for custom mapbox gl js cases where transparent 0 is expected
            # rio-tiler automatically makes nodata transparent. If the file has 0 as nodata, it'll work.
            try:
                cm = cmap.get(colormap) # Try to use user provided colourmap first
            except Exception:
                cm = cmap.get("viridis") # fallback
                
            # Render the tile to a PNG formatted byte string
            content = img.render(img_format="PNG", colormap=cm)
            
            # Return HTTP response
            return Response(content=content, media_type="image/png")
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Tile rendering error: {str(e)}")
