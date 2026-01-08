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
Notes: This grid defines the spatial alignment for all raster datasets. The files contain the CRS (EPSG:32640), Pixel size (30 m × 30 m), Pixel alignment (origin), Raster extent (bounds) and Shape (width × height) values that must be followed throughout the project.
