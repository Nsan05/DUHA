# Data Directory

The raw satellite data and processed files are too large to track in Git.
All data files are available on the project Google Drive:

**https://drive.google.com/drive/folders/1tyw4CMagENUEwCw_3vkB5nHzcJwYKfq0?usp=sharing**

---

## Directory Structure

```text
data/
├── raw/                              <- Input data (download from Google Drive)
│   ├── landsat/                      <- Landsat 9 Collection 2 L2 scenes (.TIF bands)
│   ├── sentinel2/
│   │   └── scenes/                   <- Unzipped .SAFE folders (10m/20m bands + SCL)
│   ├── viirs/                        <- VIIRS VNP21 LST NetCDF files (.nc)
│   ├── GBA/
│   │   └── OutputFiles/              <- Global Building Atlas 3m height tiles (.tif)
│   ├── overture/                     <- buildings.geojsonseq (Overture Maps footprints)
│   ├── boundaries/                   <- urban_dubai_communities.geojson
│   └── census/                       <- Dubai Pulse population/area data
│
├── intermediate/                     <- Outputs of src/features/ and src/masks/
│   ├── grids/                        <- master_grid_30m.tif + reference_grid_meta.json
│   ├── sentinel2_30m/                <- Per-scene Sentinel-2 band rasters at 30m
│   ├── urban_form/                   <- Intermediate building/road density rasters
│   └── masks/                        <- urban_mask_30m.tif, water, sand masks
│
├── final/                            <- Final outputs used by the backend API
│   ├── phase1_features/              <- All 13 aligned 30m feature rasters
│   │   ├── ndvi_30m.tif              <- NDVI (Sentinel-2 median composite)
│   │   ├── ndvi_std_30m.tif          <- NDVI spatial std (750m window)
│   │   ├── albedo_30m.tif            <- Broadband surface albedo
│   │   ├── albedo_std_30m.tif
│   │   ├── building_density_30m.tif  <- Building footprint fraction (Overture)
│   │   ├── building_density_std_30m.tif
│   │   ├── road_density_30m.tif      <- Paved road surface fraction (OSM)
│   │   ├── road_density_std_30m.tif
│   │   ├── height_30m.tif            <- Mean building height (GBA tiles)
│   │   ├── height_std_30m.tif
│   │   ├── dist_to_coast_30m.tif     <- Euclidean distance to Persian Gulf (m)
│   │   ├── sand_mask_30m.tif         <- Sand/bare soil fraction
│   │   ├── water_mask_full_30m.tif   <- Open water fraction (full scene)
│   │   ├── water_mask_urban_30m.tif  <- Open water fraction (urban extent only)
│   │   └── urban_mask_30m.tif        <- Binary urban boundary mask
│   │
│   ├── phase2_outputs/               <- Afternoon model LST anomaly raster
│   │   └── lst_anomaly_30m.tif       <- VIIRS afternoon anomaly (°C from city mean)
│   │
│   ├── phase3a_outputs/              <- Morning model LST anomaly raster
│   │   └── lst_anomaly_landsat_30m.tif
│   │
│   ├── phase3b_outputs/              <- Nighttime model LST anomaly raster
│   │   └── lst_anomaly_nighttime_30m.tif
│   │
│   ├── communities_enriched.geojson  <- Community polygons + zonal stats (API map layer)
│   ├── community_stats.json          <- Per-community statistics for the API
│   ├── phase2_training_table.csv     <- Raw VIIRS training samples
│   ├── phase2_training_table_enriched.csv <- Training samples + height + dist_to_coast
│   ├── phase3a_training_table.csv    <- Landsat morning training samples
│   └── phase3b_training_table.csv    <- VIIRS nighttime training samples
│
├── models/                           <- Trained LightGBM models (loaded by the API)
│   ├── gb_model_anomaly.joblib       <- Afternoon model
│   ├── gb_model_landsat.joblib       <- Morning model
│   ├── gb_model_nighttime.joblib     <- Nighttime model
│   ├── best_params.joblib            <- Tuned hyperparameters (afternoon)
│   ├── best_params_landsat.joblib    <- Tuned hyperparameters (morning)
│   └── best_params_nighttime.joblib  <- Tuned hyperparameters (nighttime)
│
└── model_outputs/                    <- Evaluation plots and prediction rasters
```

---

## Data Generation Pipeline

The contents of `intermediate/`, `final/`, and `models/` are fully reproducible from the `raw/` inputs using the scripts in `src/`.

### Step 1 — Feature Engineering (`src/features/`)

| Script                     | Output                                                                        |
| -------------------------- | ----------------------------------------------------------------------------- |
| `sentinel2.py`             | Sentinel-2 median composites → `intermediate/sentinel2_30m/`                  |
| `buildings.py`             | Overture Maps footprints → `intermediate/urban_form/building_density_30m.tif` |
| `roads.py`                 | OSM drive network → `intermediate/urban_form/road_density_30m.tif`            |
| `rasterize_height_30m.py`  | GBA 3m tiles → `final/phase1_features/height_30m.tif`                         |
| `coast_distance_raster.py` | Euclidean distance transform → `final/phase1_features/dist_to_coast_30m.tif`  |
| `viirs.py`                 | VIIRS NetCDF loader (used by pipeline assembly)                               |

### Step 2 — Mask Generation (`src/masks/`)

| Script          | Output                                                |
| --------------- | ----------------------------------------------------- |
| `masks.py`      | `urban_mask_30m.tif`                                  |
| `water_mask.py` | `water_mask_full_30m.tif`, `water_mask_urban_30m.tif` |
| `sand_mask.py`  | `sand_mask_30m.tif`                                   |

### Step 3 — Feature Finalization (`src/pipeline_assembly/`)

| Script                           | Output                                                                                         |
| -------------------------------- | ---------------------------------------------------------------------------------------------- |
| `finalize_phase1.py`             | Validates and copies all features → `final/phase1_features/`                                   |
| `assemble_training_data.py`      | Builds `phase2_training_table.csv` (afternoon/VIIRS)                                           |
| `process_gba.py`                 | Aggregates GBA height tiles per VIIRS pixel → adds `height_mean`, `height_std` to enriched CSV |
| `coast_distance.py`              | Samples dist_to_coast raster at each training pixel → adds `dist_to_coast_m` to enriched CSV   |
| `assemble_landsat_training.py`   | Builds `phase3a_training_table.csv` (morning/Landsat)                                          |
| `assemble_nighttime_training.py` | Builds `phase3b_training_table.csv` (nighttime/VIIRS)                                          |

### Step 4 — Model Training (`src/phase2_model/`, `src/phase3_model/`)

| Script                            | Output                                |
| --------------------------------- | ------------------------------------- |
| `phase2_model/tune.py`            | `models/best_params.joblib`           |
| `phase2_model/train.py`           | `models/gb_model_anomaly.joblib`      |
| `phase3_model/tune_landsat.py`    | `models/best_params_landsat.joblib`   |
| `phase3_model/train_landsat.py`   | `models/gb_model_landsat.joblib`      |
| `phase3_model/tune_nighttime.py`  | `models/best_params_nighttime.joblib` |
| `phase3_model/train_nighttime.py` | `models/gb_model_nighttime.joblib`    |

### Step 5 — Frontend Prep (`src/frontend_prep/`)

| Script                   | Output                                                        |
| ------------------------ | ------------------------------------------------------------- |
| `join_population.py`     | Joins Dubai Pulse census data onto community boundaries       |
| `compute_zonal_stats.py` | Computes zonal feature stats per community                    |
| `export_communities.py`  | `final/communities_enriched.geojson` + `community_stats.json` |
