"""
Landsat Collection 2 Level-2 Surface Temperature Feature Processor

Handles loading ST_B10 (Surface Temperature) and QA_PIXEL (Quality Control),
applies the correct scale and offset to convert to Kelvin,
and masks out clouds and shadows based on QA bit flags.
"""

import rasterio
import numpy as np
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Landsat Collection 2 L2 ST Scale and Offset
ST_SCALE = 0.00341802
ST_OFFSET = 149.0

def load_landsat_scene(scene_dir):
    """
    Loads Landsat Collection 2 LST and QA data from a given scene directory.
    
    Args:
        scene_dir (Path or str): Path to the single scene directory containing .TIF files.
        
    Returns:
        dict: {
            'scene_id': str,
            'lst': array (H, W) (Kelvin, cleaned),
            'transform': rasterio affine transform,
            'crs': rasterio crs,
            'bounds': rasterio bounds,
            'shape': (H, W)
        } or None if loading fails.
    """
    scene_dir = Path(scene_dir)
    scene_id = scene_dir.name
    logger.info(f"Loading Landsat Scene: {scene_id}")
    
    # Locate required bands
    st_files = list(scene_dir.rglob("*_ST_B10.TIF"))
    qa_files = list(scene_dir.rglob("*_QA_PIXEL.TIF"))
    
    if not st_files or not qa_files:
        logger.error(f"Missing required TIF files in {scene_dir}")
        return None
        
    st_path = st_files[0]
    qa_path = qa_files[0]
    
    try:
        # 1. Load QA mask
        with rasterio.open(qa_path) as qa_src:
            qa_data = qa_src.read(1)
            
        # 2. Load ST data and metadata
        with rasterio.open(st_path) as st_src:
            st_data = st_src.read(1)
            transform = st_src.transform
            crs = st_src.crs
            bounds = st_src.bounds
            shape = st_data.shape
            
        # 3. Apply QA masking and scaling
        clean_lst, valid_mask = process_landsat_lst(st_data, qa_data)
        
        # Early exit if cloud entirely covered the area
        if np.sum(valid_mask) == 0:
            logger.warning(f"No valid pixels in {scene_id} after QA mask.")
            return None
        
        return {
            'scene_id': scene_id,
            'lst': clean_lst,
            'transform': transform,
            'crs': crs,
            'bounds': bounds,
            'shape': shape
        }
        
    except Exception as e:
        logger.error(f"Failed to load Landsat scene {scene_id}: {e}")
        return None

def process_landsat_lst(st_data, qa_data):
    """
    Applies QA filtering, scaling, and offset to raw Landsat ST_B10 data.
    
    QA_PIXEL Bits (Collection 2):
    - Bit 1: Dilated Cloud
    - Bit 3: Cloud
    - Bit 4: Cloud Shadow
    
    Args:
        st_data: 2D array of raw ST_B10 DN values
        qa_data: 2D array of QA_PIXEL values
        
    Returns:
        tuple: (lst_kelvin_array, valid_mask)
    """
    # Ensure integer for bitwise operations
    if not np.issubdtype(qa_data.dtype, np.integer):
        qa_data = qa_data.astype(int)
        
    # Creating mask fro all the bad pixels
    dilated_cloud = (qa_data & (1 << 1)) > 0
    cloud = (qa_data & (1 << 3)) > 0
    cloud_shadow = (qa_data & (1 << 4)) > 0
    
    # 0 is the fill value for Landsat ST
    fill_or_missing = (st_data == 0)
    
    invalid_mask = dilated_cloud | cloud | cloud_shadow | fill_or_missing
    valid_mask = ~invalid_mask
    
    # Create empty output array
    lst_kelvin = np.full(st_data.shape, np.nan, dtype=np.float32)
    
    # Apply scale and offset ONLY to valid pxls
    # K = DN * 0.00341802 + 149.0
    valid_st = st_data[valid_mask].astype(np.float32)
    lst_kelvin[valid_mask] = valid_st * ST_SCALE + ST_OFFSET
    
    dropped_pct = 100 * (np.sum(invalid_mask) / st_data.size)
    logger.info(f"Quality Filter: Dropped {dropped_pct:.1f}% of pixels (Clouds/Shadows/Fill).")
    
    return lst_kelvin, valid_mask
