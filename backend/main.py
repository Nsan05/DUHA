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

# --- LIFESPAN MANAGER ---
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
    """Returns the full enriched GeoJSON for Mapbox to draw the map layers."""
    return state.communities_geojson

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
