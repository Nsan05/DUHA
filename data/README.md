# Data Access Instructions

The raw satellite data and processed files are too large to host on GitHub.
Please download them from the Project Google Drive.

**https://drive.google.com/drive/folders/1tyw4CMagENUEwCw_3vkB5nHzcJwYKfq0?usp=sharing**

## Installation Steps

1. Download the `data.zip` (or individual folders) from the Drive link above.
2. Unzip/Place the files to match the following structure EXACTLY:

```text
data/
├── raw/
│   ├── landsat/
│   │   ├── lst/       <-- Place Landsat 8/9 Band 10 TIFs here
│   │   └── metadata/  <-- MTL.txt files here
│   ├── sentinel2/
│   │   ├── scenes/    <-- Place .SAFE folders or unzipped .tif bands here
│   │   └── metadata/
│   ├── viirs/
│   │   ├── daytime/   <-- Place VIIRS .h5 or .tif files here
│   │   └── metadata/
│   ├── osm/           <-- Place .pbf or .shp files for Dubai here
│   └── boundaries/    <-- Place urban_dubai_communities.geojson here
```

## Data Manifest

- **Sentinel-2**: Level-2A surface reflectance (dates aligned with Landsat/VIIRS).
- **Landsat 8/9**: Collection 2 Level 2 Surface Temperature (Band 10).
- **VIIRS**: VNP21 Land Surface Temperature (Daytime).
- **OSM**: OpenStreetMap vector data (Roads, Buildings, Water).
- **Boundaries**: Dubai urban community shapefiles/GeoJSON.
