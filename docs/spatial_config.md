# Spatial Configuration

## Coordinate Reference System (CRS)

Project CRS: EPSG:32640 (UTM Zone 40N)  
Units: meters  
Notes: Selected to ensure accurate distance, area, and raster-based analysis over Dubai.

## Master Raster Grid

Resolution: 30 m  
Source: Landsat 9 (LC09_L2SP_160043_20250812)  
CRS: EPSG:32640  
Dimensions: 7691 x 7841  
Origin (Top-Left): 201585.0, 2833815.0  
Path: `data/intermediate/grids/master_grid_30m.tif`  
Notes: This grid defines the spatial alignment for all raster datasets. The files contain the CRS (EPSG:32640), Pixel size (30 m × 30 m), Pixel alignment (origin), Raster extent (bounds) and Shape (width × height) values that must be followed throughout the project. It ensures all the pixels will be properly aligned and the same size for all raster datasets.

## Urban Mask

Type: Binary Raster (1=Urban, 0=Background)  
Source: `urban_dubai_communities.geojson` (Dissolved)  
Path: `data/intermediate/masks/urban_mask_30m.tif`  
Note: Urban extent is defined by dissolving all community boundary polygons into a single urban geometry and rasterising this geometry onto the 30 m master grid. Pixels inside the urban extent are assigned a value of 1, and all other pixels are assigned 0.

### Sand Mask (Control Variable)

- **Purpose**: Identify natural bare soil/sand surfaces to control for their distinct thermal behavior.
- **File**: `data/intermediate/masks/sand_mask_30m.tif`
- **Logic**: `(Urban==1) & (NDWI < -0.07) & (NDVI < 0.15) & (BSI > 0.08) & (Albedo > 0.25)`
- **Stats**: Covers ~34.47% of the Urban Area.
- **Note**: Albedo (>0.25) strongly filters out water; BSI (>0.08) ensures high confidence in soil content.

### Water Mask

- **Purpose**: Identify open water bodies (Creek, Canals, Coast) to exclude them from heat analysis.
- **File**: `data/intermediate/masks/water_mask_30m.tif` (Binary 0/1)
- **Logic**: `(NDWI > 0) AND (Urban Mask == 1)`
- **Stats**: ~3.15% of Urban Area.

## Sentinel-2 Derived Grids (30m)

These files represent the median physical properties of the surface over the observation period, aggregated from 10m to 30m.

| Feature    | Filename         | Description                             | Logic                                                                                 |
| :--------- | :--------------- | :-------------------------------------- | :------------------------------------------------------------------------------------ |
| **NDVI**   | `ndvi_30m.tif`   | Vegetation Density (-1 to 1)            | `(NIR - Red) / (NIR + Red)`                                                           |
| **Albedo** | `albedo_30m.tif` | Broadband Surface Reflectivity (0 to 1) | Weighted Spectral IntegrationΣ (Weight_i \* Band_i) based on Solar Irradiance (ESUN). |
| **NDWI**   | `ndwi_30m.tif`   | Water Index (-1 to 1)                   | `(Green - NIR) / (Green + NIR)`                                                       |
| **BSI**    | `bsi_30m.tif`    | Bare Soil Index (-1 to 1)               | `((SWIR1 + Red) - (NIR + Blue)) / ((SWIR1 + Red) + (NIR + Blue))`                     |

**Processing Note**: These were generated using a Median Composite of all cloud-free pixels from the available Sentinel-2 scenes.

## Urban Form Grids (30m)

These metrics quantify the physical structure of the city, generated via **Sub-pixel Super-sampling (10x)** to ensure accurate fractional coverage (0.00 - 1.00) even at 30m resolution.

| Feature              | Filename                   | Description                                      | Methodology                                                                                              |
| :------------------- | :------------------------- | :----------------------------------------------- | :------------------------------------------------------------------------------------------------------- |
| **Building Density** | `building_density_30m.tif` | Fraction of pixel covered by building footprints | Source: **Overture Maps**. Vector-to-Raster with 10x super-sampling for fractional accuracy.             |
| **Road Density**     | `road_density_30m.tif`     | Fraction of pixel covered by paved road surface  | Source: **OSM** (`network_type='drive'`). Widths imputed from lane counts + class medians. 10x sampling. |

**Methodology Note**:

- **Building Density**: Derived from high-precision Overture Maps footprints.
- **Road Density**: Derived from OpenStreetMap centerlines (Drive network).
  - **Width Estimation**: Observed `lanes` \* 3.5m. Missing lanes imputed using local median lane count per `highway` class.
  - **Buffering**: Centerlines buffered by `width / 2` to create realistic surface polygons.
  - **Clip**: Strictly clipped to the `urban_dubai_communities` boundary.
