
import json
import rasterio
from rasterio.warp import reproject, Resampling
from rasterio.transform import Affine
import numpy as np
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Paths
GBA_DIR = Path("data/raw/GBA/OutputFiles")
REF_GRID_META = Path("data/intermediate/grids/reference_grid_meta.json")
OUTPUT_PATH = Path("data/final/phase1_features/height_30m.tif")

# Height threshold: values <= 2m are ground noise, set to 0
GROUND_THRESHOLD = 2.0

def main():
    """
    Mosaic GBA height tiles (3m resolution) onto the 30m reference grid.
    
    Strategy:
    1. Create an empty output array matching the reference grid (30m).
    2. For each GBA tile (3m), reproject/resample it onto the output grid using average resampling.
    3. Accumulate heights (sum + count) to handle tile overlaps correctly.
    4. Save the final averaged height raster.
    """
    
    # 1. Read reference grid metadata from JSON
    logger.info(f"Reading reference grid: {REF_GRID_META}")
    with open(REF_GRID_META) as f:
        meta = json.load(f)
    
    ref_transform = Affine(*meta['transform'])
    ref_crs = meta['crs']
    ref_shape = (meta['height'], meta['width'])  # (7841, 7691)
    
    logger.info(f"  Shape: {ref_shape}, CRS: {ref_crs}, Res: 30m")
    
    # 2. Prepare output arrays (accumulate sum + count for averaging)
    height_sum = np.zeros(ref_shape, dtype=np.float64)
    height_count = np.zeros(ref_shape, dtype=np.int32)
    
    # 3. Process each GBA tile
    tiles = sorted(GBA_DIR.glob("*.tif"))
    logger.info(f"Found {len(tiles)} GBA tiles to process")
    
    for i, tile_path in enumerate(tiles):
        logger.info(f"Processing tile {i+1}/{len(tiles)}: {tile_path.name}")
        
        with rasterio.open(tile_path) as src:
            # Read the 3m tile
            data_3m = src.read(1).astype(np.float32)
            
            # Apply ground mask: values <= 2m → 0 (ground noise)
            data_3m[data_3m <= GROUND_THRESHOLD] = 0
            data_3m[data_3m == src.nodata] = 0
            
            # Create a count mask (1 where we have valid building height, 0 otherwise)
            valid_3m = (data_3m > 0).astype(np.float32)
            
            # Reproject HEIGHT SUM to 30m grid (sum resampling)
            tile_sum = np.zeros(ref_shape, dtype=np.float64)
            reproject(
                source=data_3m,
                destination=tile_sum,
                src_transform=src.transform,
                src_crs=src.crs,
                dst_transform=ref_transform,
                dst_crs=ref_crs,
                resampling=Resampling.average,
                dst_nodata=0
            )
            
            # Reproject COUNT to 30m grid (to know how many valid 3m pixels fell into each 30m cell)
            tile_count = np.zeros(ref_shape, dtype=np.float64)
            reproject(
                source=valid_3m,
                destination=tile_count,
                src_transform=src.transform,
                src_crs=src.crs,
                dst_transform=ref_transform,
                dst_crs=ref_crs,
                resampling=Resampling.average,
                dst_nodata=0
            )
            
            # Accumulate (average resampling already handles the 3m→30m aggregation)
            # tile_sum now contains the average height per 30m pixel from this tile
            # tile_count contains the fraction of valid 3m pixels per 30m cell
            mask = tile_count > 0
            height_sum[mask] += tile_sum[mask]
            height_count[mask] += 1  # Count how many tiles contributed to each pixel
            
            n_valid = np.sum(mask)
            logger.info(f"  -> {n_valid} pixels received height data from this tile")
    
    # 4. Compute final average (handle tile overlaps)
    logger.info("Computing final averaged height raster...")
    final_height = np.zeros(ref_shape, dtype=np.float32)
    overlap_mask = height_count > 0
    final_height[overlap_mask] = (height_sum[overlap_mask] / height_count[overlap_mask]).astype(np.float32)
    
    # Stats
    building_pixels = np.sum(final_height > 0)
    total_pixels = ref_shape[0] * ref_shape[1]
    logger.info(f"Height Stats:")
    logger.info(f"  Pixels with buildings: {building_pixels} ({building_pixels/total_pixels:.1%})")
    logger.info(f"  Min (non-zero): {final_height[final_height > 0].min():.1f} m")
    logger.info(f"  Max: {final_height.max():.1f} m")
    logger.info(f"  Mean (non-zero): {final_height[final_height > 0].mean():.1f} m")
    
    # 5. Save
    out_profile = {
        'driver': 'GTiff',
        'dtype': 'float32',
        'width': ref_shape[1],
        'height': ref_shape[0],
        'count': 1,
        'crs': ref_crs,
        'transform': ref_transform,
        'nodata': 0,
        'compress': 'lzw'
    }
    
    logger.info(f"Saving to: {OUTPUT_PATH}")
    with rasterio.open(OUTPUT_PATH, 'w', **out_profile) as dst:
        dst.write(final_height, 1)
    
    logger.info("Done!")

if __name__ == "__main__":
    main()
