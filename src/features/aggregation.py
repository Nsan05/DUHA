import rasterio
import numpy as np
import logging
from rasterio.windows import Window

logger = logging.getLogger(__name__)

# Constants
VIIRS_RES = 750  # meters
SUB_RES = 30     # meters
WINDOW_SIZE = int(VIIRS_RES / SUB_RES) # 25 pixels
HALF_WINDOW = WINDOW_SIZE // 2
MIN_URBAN_FRACTION = 0.3 # 30%

def get_window(x, y, transform):
    """
    Calculates the rasterio Window for a given metric coordinate.
    
    Args:
        x, y: Projected coordinates (EPSG:32640) of the VIIRS pixel CENTER.
        transform: Affine transform of the 30m raster.
        
    Returns:
        Window object or None if out of bounds.
    """
    # Convert metric coord to pixel row/col
    # ~ is the inverse transform (coord -> pixel)
    col, row = ~transform * (x, y)
    
    # Define window bounds (top-left)
    # col, row are floats identifying the center. 
    # We want a WINDOW_SIZE x WINDOW_SIZE box centered on this.
    
    # Top-Left Pixel Index - the col, row points at the center of the pixel, so we need to subtract half the window size to get the top-left
    start_col = int(col - HALF_WINDOW)
    start_row = int(row - HALF_WINDOW)
    
    return Window(start_col, start_row, WINDOW_SIZE, WINDOW_SIZE)

def aggregate_pixel(viirs_x, viirs_y, raster_handles):
    """
    Aggregates 30m features for a single VIIRS pixel location.
    
    Args:
        viirs_x, viirs_y: Center coordinates (meters).
        raster_handles: Dict of {filename: open_rasterio_handle}.
        
    Returns:
        dict: Aggregated features (e.g., {'ndvi_mean': 0.4, ...}) or None if invalid.
    """
    
    # 1. Get Urban Mask Handle
    # The mask file is expected to be open and passed in raster_handles
    # We need to identifying which handle corresponds to urban_mask_30m.tif
    
    urban_handle = None
    for fname, handle in raster_handles.items():
        if "urban_mask_30m.tif" in fname:
            urban_handle = handle
            break
            
    if not urban_handle:
        logger.error("Urban mask handle not found!")
        return None
        
    # 2. Define Window
    # Use accurate georeferencing from the mask
    # We use get_window helper which does ~transform * (x,y)
    
    window = get_window(viirs_x, viirs_y, urban_handle.transform)
    
    # 3. Read Urban Mask
    try:
        # boundless=True is critical for edge pixels so even if the window goes of the edge, it does not crash
        urban_data = urban_handle.read(1, window=window, boundless=True, fill_value=0)
    except Exception:
        return None
        
    # Check shape - ususally would never happpen but just incase of corrupt files 
    if urban_data.shape != (WINDOW_SIZE, WINDOW_SIZE):
        return None
        
    # 4. Compute Urban Fraction
    urban_pixels = np.sum(urban_data == 1)
    total_pixels = urban_data.size # Should be 25x25 = 625
    urban_fraction = urban_pixels / total_pixels
    
    # 5. FILTER
    if urban_fraction < MIN_URBAN_FRACTION:
        return None
        
    # 6. Aggregate Features
    results = {
        "urban_fraction": urban_fraction,
        "valid_pixels": urban_pixels
    }
    
    # Boolean mask for extraction (Where is it actually urban?)
    urban_bool = (urban_data == 1)
    
    for fname, src in raster_handles.items():
        if src == urban_handle:
            continue
            
        # Read feature data
        data = src.read(1, window=window, boundless=True, fill_value=np.nan)
        
        # Mask by Urban Pixels
        relevant_data = data[urban_bool]
        
        # Filter NaNs
        valid_feature_data = relevant_data[~np.isnan(relevant_data)]
        
        if valid_feature_data.size == 0:
            mean_val = np.nan
        else:
            mean_val = np.mean(valid_feature_data)
        
        # Determine output name - # Turn a path like "data/ndvi_30m.tif" into "ndvi"
        base_name = fname.split("/")[-1].replace("_30m.tif", "")
        
        if "mask" in fname:
            # For masks, mean = fraction
            results[f"{base_name}_fraction"] = mean_val
        else:
            # Continuous vars
            results[f"{base_name}_mean"] = mean_val
            
    return results
