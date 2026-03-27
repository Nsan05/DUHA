# Dubai Urban Heat Island Analysis

### Final Year Project - Nithin Santhosh

> A high-resolution urban climate intelligence platform that maps, explains, and simulates the mitigation of the Urban Heat Island (UHI) effect across Dubai's communities.

---

## Overview

This project delivers an end-to-end pipeline for analysing urban heat at **30-metre pixel resolution** across Dubai. It combines satellite remote sensing, machine learning, and an interactive web interface so planners and researchers can explore heat patterns, understand their drivers, and simulate the impact of urban greening or albedo interventions.

Three separate LightGBM models cover different times of day, capturing both diurnal and nocturnal heat dynamics:

| Time Slot     | Data Source                | Target                |
| ------------- | -------------------------- | --------------------- |
| **Morning**   | Landsat 9 LST              | Pre-noon LST anomaly  |
| **Afternoon** | VIIRS downscaled to 30m    | Peak-heat LST anomaly |
| **Night**     | VIIRS Nighttime downscaled | Nocturnal LST anomaly |

---

## Project Structure

```
FYP/
├── backend/          # FastAPI REST API — model inference, raster sampling, SHAP
├── frontend/         # Next.js + Mapbox GL JS interactive map dashboard
├── src/              # Offline data preparation & model training scripts
│   ├── features/         # Feature engineering (NDVI, albedo, building/road density)
│   ├── masks/            # Urban, sand & water mask generation
│   ├── phase2_model/     # Afternoon VIIRS downscaling model (tune / train / interpret)
│   ├── phase3_model/     # Morning (Landsat) & Night model pipelines
│   ├── phase2_downscaling/
│   ├── pipeline_assembly/
│   └── frontend_prep/    # Generates community stats GeoJSON for the API
├── data/             # Raw/intermediate/final raster & vector datasets (not tracked)
├── docs/             # Spatial configuration & methodology documentation
├── notebooks/        # Exploratory analysis notebooks
└── outputs/          # Model evaluation outputs and figures
```

---

## Key Features

- 🗺️ **Interactive Mapbox Map** : community-level heat choropleth with 30m pixel drill-down
- 🤖 **SHAP Explainability** : per-pixel AI explanation of which urban features drive heat
- 🌿 **Intervention Simulator** : adjust NDVI, albedo, building density and see predicted temperature change in real time
- 📊 **Community Dashboard** : radar chart, heat priority ranking, and diurnal anomaly comparison
- 🟥 **Priority Community Filter** : dynamically identifies the most heat-vulnerable communities using a 95th-percentile threshold

---

## Tech Stack

| Layer        | Technology                                                                   |
| ------------ | ---------------------------------------------------------------------------- |
| Frontend     | Next.js 16, React 19, TypeScript, Mapbox GL JS, Recharts                     |
| Backend      | FastAPI, Python, Rasterio, rio-tiler                                         |
| ML Models    | LightGBM, SHAP, scikit-learn                                                 |
| Geospatial   | EPSG:32640 (UTM Zone 40N), 30m resolution rasters                            |
| Data Sources | Sentinel-2, Landsat 9, VIIRS, Overture Maps, OpenStreetMap, Dubai Pulse, GBA |

---

## Prerequisites

- **Python 3.10+** (tested with 3.10 and 3.11)
- **Node.js 18+** and **npm**
- A **Mapbox** account with an access token (free tier works)

---

## Running Locally

### 1. Clone the Repository

```bash
git clone <repo-url>
cd FYP
```

### 2. Set Up the Data Folder

The `data/` directory is not tracked in Git due to its size. Download it from the project Google Drive and place it in the project root so it matches the structure below:

```
data/
├── raw/                     <- Raw satellite & vector inputs
│   ├── landsat/
│   ├── sentinel2/scenes/
│   ├── viirs/
│   ├── GBA/OutputFiles/
│   ├── overture/
│   ├── boundaries/          <- Must contain urban_dubai_communities.geojson
│   └── census/              <- Must contain Population_by_community.xlsx
├── intermediate/
├── final/
│   ├── phase1_features/     <- All 13 aligned 30m feature rasters (.tif)
│   ├── phase2_outputs/      <- lst_anomaly_30m.tif
│   ├── phase3a_outputs/     <- lst_anomaly_landsat_30m.tif
│   ├── phase3b_outputs/     <- lst_anomaly_nighttime_30m.tif
│   ├── communities_enriched.geojson
│   └── community_stats.json
├── models/                  <- Trained LightGBM .joblib files
│   ├── gb_model_anomaly.joblib
│   ├── gb_model_landsat.joblib
│   └── gb_model_nighttime.joblib
└── model_outputs/
```

> **The backend requires `data/final/`, `data/models/`, and `data/final/communities_enriched.geojson` at a minimum to start.** See `data/README.md` for the full directory layout and the Google Drive link.

### 3. Backend (FastAPI)

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

The API will be available at `http://localhost:8000`. Interactive docs at `http://localhost:8000/docs`.

### 4. Frontend (Next.js)

Create a `.env.local` file in the `frontend/` directory with your Mapbox token:

```bash
cd frontend
echo "NEXT_PUBLIC_MAPBOX_TOKEN=your_mapbox_token_here" > .env.local
```

Then install and run:

```bash
npm install
npm run dev
```

The app will be available at `http://localhost:3000`.

> **Environment Variables:**
> - `NEXT_PUBLIC_MAPBOX_TOKEN` **(required)** — your Mapbox GL access token. The map will not render without it.
> - `NEXT_PUBLIC_API_URL` *(optional)* — backend URL, defaults to `http://localhost:8000`.

---

## API Endpoints

| Method | Endpoint                             | Description                                                     |
| ------ | ------------------------------------ | --------------------------------------------------------------- |
| `GET`  | `/api/communities`                   | Returns enriched community GeoJSON + global feature ranges      |
| `POST` | `/api/pixel`                         | Samples all features & anomalies at a lat/lon coordinate        |
| `POST` | `/api/predict`                       | Runs a modified feature vector through all 3 models             |
| `POST` | `/api/predict-batch`                 | Batch prediction with recomputed spatial std values             |
| `POST` | `/api/shap`                          | Returns SHAP feature contributions + plain-language explanation |
| `GET`  | `/api/community/{id}/pixels`         | Returns 30m pixel grid for a community with anomaly values      |
| `GET`  | `/api/tiles/{layer}/{z}/{x}/{y}.png` | Dynamic XYZ raster tile server                                  |

---

## Spatial Configuration

- **CRS:** EPSG:32640 (UTM Zone 40N)
- **Resolution:** 30 m × 30 m
- **Reference Grid:** Landsat 9 scene `LC09_L2SP_160043_20250812`
- **Urban Extent:** Defined by dissolved Dubai community boundary polygons

---

_BSc Computer Science - Final Year Project, 2025–26_
