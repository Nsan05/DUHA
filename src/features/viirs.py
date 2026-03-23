import netCDF4 as nc
import numpy as np
import pyproj
import logging

logger = logging.getLogger(__name__)

# Project CRS (UTM Zone 40N)
TARGET_CRS = "EPSG:32640"

def load_viirs_scene(nc_path):
    """
    Loads VNP21 NetCDF file and extracts relevant arrays.
    
    Args:
        nc_path (Path): Path to .nc file
        
    Returns:
        dict: {
            'lat': array (H, W),
            'lon': array (H, W),
            'lst': array (H, W) (Kelvin),
            'qf': array (H, W)  (Quality Flags)
        }
    """
    logger.info(f"Loading VIIRS Scene: {nc_path.name}")
    
    try:
        ds = nc.Dataset(nc_path)
        
        # VNP21 structure usually has groups. 
        # Adjust based on standard VNP21 format:
        # /HDFEOS/SWATHS/VNP_21_Swath/Geolocation Fields/Latitude
        # /HDFEOS/SWATHS/VNP_21_Swath/Data Fields/LST
    
        
        if 'VIIRS_Swath_LSTE' in ds.groups:
            swath = ds.groups['VIIRS_Swath_LSTE']
            geo = swath.groups['Geolocation Fields']
            data = swath.groups['Data Fields']
            
            # Note: Variable names from inspection
            lat = geo.variables['latitude'][:] # row represents as the satellitle moves along its path , column represents the position of the pixel as it moves from left to right along the path.
            lon = geo.variables['longitude'][:] 
            lst = data.variables['LST'][:]
            qf = data.variables['QC'][:] 
            
            return {
                'lat': np.array(lat),
                'lon': np.array(lon),
                'lst': np.array(lst),
                'qc': np.array(qf)
            }
        elif 'HDFEOS' in ds.groups:
             # Legacy/Standard fallback
            swath = ds.groups['HDFEOS'].groups['SWATHS'].groups['VNP_21_Swath']
            geo = swath.groups['Geolocation Fields']
            data = swath.groups['Data Fields']
            
            lat = geo.variables['Latitude'][:]
            lon = geo.variables['Longitude'][:]
            lst = data.variables['LST'][:]
            qf = data.variables['QC'][:] 
            
            return {
                'lat': np.array(lat),
                'lon': np.array(lon),
                'lst': np.array(lst),
                'qc': np.array(qf)
            }
        else:
            # Fallback debug
            available = list(ds.groups.keys())
            raise ValueError(f"Unknown NetCDF Structure. Found groups: {available}")
            
    except Exception as e:
        logger.error(f"Failed to load VIIRS file: {e}")
        raise

def transform_coords(lat_array, lon_array):
    """
    Transforms Lat/Lon arrays to Project CRS (UTM 40N).
    
    Args:
        lat_array: 2D numpy array of latitudes
        lon_array: 2D numpy array of longitudes
        
    Returns:
        tuple: (x_array, y_array) in meters (EPSG:32640)
    """
    logger.info("Transforming coordinates to EPSG:32640...")
    
    # Define Projections
    wgs84 = pyproj.CRS("EPSG:4326")
    utm40n = pyproj.CRS(TARGET_CRS)
    transformer = pyproj.Transformer.from_crs(wgs84, utm40n, always_xy=True)
    
    # Transform (this handles arrays efficiently)
    # Note: Transformer expects (x, y) -> (lon, lat)
    xx, yy = transformer.transform(lon_array, lat_array)
    
    return xx, yy

def filter_quality(lst, qc):
    """
    Applies Quality Flags to mask invalid LST pixels.
    
    VNP21 QC Details (simplified):
    - Bit 0-1: Mandatory QA (00=Good, 01=Good/marginal, 10=Cloud, 11=Poor)
    
    Args:
        lst (array): LST Temperature (Kelvin)
        qc (array): Quality Control Flags
        
    Returns:
        masked_array: LST with invalid pixels masked (NaN)
    """
    # Ensure integer type for bitwise operations
    if not np.issubdtype(qc.dtype, np.integer):
        qc = qc.astype(int)
        
    # Extract Bits 0-1 (Mandatory QA)
    # checks the last two bits of the qc (long num with nlots of info but we only care about the last two digits for quality) array and print 00 or 01 or 10 or 11 depending on comparison
    mandatory_qa = qc & 0b11
    
    # Valid = 00 (Good) or 01 (Marginal) -> Allow both 
    # Update: 00 = Pixel produced, good quality
    
    valid_mask = (mandatory_qa == 0) # only keeps the good quality pixels
    
    # Remove pixels where LST is 0 or NaN (fill values)
    # LST valid range is approx 200K - 350K. 0 is definitely fill.
    valid_mask &= (lst > 0)
    valid_mask &= (~np.isnan(lst))
    
    # Create masked array (or just set to NaN)
    clean_lst = lst.copy()
    clean_lst[~valid_mask] = np.nan
    
    dropped_pct = 100 * (1 - np.sum(valid_mask) / list(lst.flatten().shape)[0])
    logger.info(f"Quality Filter: Dropped {dropped_pct:.1f}% of pixels (Clouds/Poor QA).")
    
    return clean_lst, valid_mask
