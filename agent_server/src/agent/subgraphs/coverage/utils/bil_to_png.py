import os
import json
import numpy as np
import rasterio
from rasterio.errors import RasterioIOError
from PIL import Image
from datetime import datetime, timezone
from agent.config.array_type_mapper import ArrayTypeMapper

def convert_bil_to_rgb_png(base_filename, output_dir=None, array_type=""):
    """
    Converts a .bil file to a 24-bit RGB encoded PNG with a companion JSON metadata file.
    The EPSG code is detected automatically from the BIL file's embedded CRS.
    
    Args:
        base_filename (str): The base name of the file WITHOUT extension (e.g., "my_data").
                             The function expects "my_data.bil" and "my_data.hdr" to exist.
        output_dir (str, optional): Directory to save output PNG and JSON files.
                                    If None, outputs are saved in the same directory as input.
        array_type (str, optional): Array type label prepended to output filenames.
    
    Returns:
        dict: {"success": bool, "error": str (if failed), "filename": str (if success), "basename": str (if success)}
    """
    
    # 1. Define File Paths
    input_bil = f"{base_filename}.bil"
    input_hdr = f"{base_filename}.hdr"
    
    # Extract just the filename without path for output
    file_basename = os.path.basename(base_filename)
    file_basename = f"{array_type}_{file_basename}"
    base_filename = f"{array_type}_{base_filename}"
    # Determine output paths based on output_dir
    if output_dir:
        output_png = os.path.join(output_dir, f"{file_basename}.png")
        output_json = os.path.join(output_dir, f"{file_basename}.json")
    else:
        output_png = f"{base_filename}.png"
        output_json = f"{base_filename}.json"
    
    # 2. Validation Checks
    if not os.path.exists(input_bil):
        return {"success": False, "error": f".bil file not found: {input_bil}"}
    if not os.path.exists(input_hdr):
        return {"success": False, "error": f".hdr file not found: {input_hdr}"}

    try:
        # 3. Read Data using Rasterio
        with rasterio.open(input_bil) as src:
            data = src.read(1)
            
            width = src.width
            height = src.height
            bounds = src.bounds
            detected_epsg = src.crs.to_epsg() if src.crs else None
            
            nodata_val = src.nodata
            
            # If NoData isn't defined in header, assume a default (teoco standard)
            if nodata_val is None:
                nodata_val = -9999.0

    except RasterioIOError as e:
        return {"success": False, "error": f"Rasterio could not open the file. Check your .hdr format. Details: {e}"}
    except Exception as e:
        return {"success": False, "error": f"Unexpected error while reading: {e}"}

    # 4. Filter Valid Data
    # Create a boolean mask: True where data is VALID
    # We check for NoData value, NaNs, and Infinite values
    valid_mask = (data != nodata_val) & (~np.isnan(data)) & (~np.isinf(data))

    # Check if the file is completely empty/invalid
    if not np.any(valid_mask):
        return {"success": False, "error": f"File {input_bil} contains only NoData ({nodata_val}) or NaNs"}

    # 5. Calculate Dynamic Range (Min/Max) from VALID pixels only
    # Convert to float to ensure JSON serializability later
    data_min = float(data[valid_mask].min())
    data_max = float(data[valid_mask].max())

    print(f"Processing {base_filename}...")
    print(f"  - Grid Size: {width} x {height}")
    print(f"  - Valid Data Range: {data_min:.4f} to {data_max:.4f}")

    # Safety: If min == max (flat data), add a tiny epsilon to prevent divide-by-zero
    if data_max == data_min:
        print("  - Warning: Data is flat (min == max). Adjusting max slightly.")
        data_max = data_min + 1.0

    # 6. Normalize Data (Vectorized Operation)
    # Create a blank array for normalized values
    normalized = np.zeros_like(data, dtype=np.float64)
    
    # Apply formula only to valid pixels: (val - min) / (max - min)
    normalized[valid_mask] = (data[valid_mask] - data_min) / (data_max - data_min)
    
    # Set NoData pixels to 0.0 (or you could choose another strategy)
    normalized[~valid_mask] = 0.0

    # 7. Encode to 24-bit Integer
    # Scale 0.0-1.0 to 0-16,777,215
    int24 = (normalized * 16777215).astype(np.uint32)

    # 8. Split into RGB Channels (Vectorized)
    # R: Top 8 bits, G: Middle 8 bits, B: Bottom 8 bits
    r = (int24 >> 16) & 0xFF
    g = (int24 >> 8) & 0xFF
    b = int24 & 0xFF

    # Stack into (Height, Width, 3) image array
    rgb_image = np.stack([r, g, b], axis=-1).astype(np.uint8)

    # 9. Save PNG Image
    try:
        Image.fromarray(rgb_image).save(output_png, compress_level=6)
        print(f"  - Saved Image: {output_png}")
    except Exception as e:
        return {"success": False, "error": f"Failed to save PNG: {e}"}

    # 10. Save JSON Metadata
    # Generate timestamp in ISO 8601 format
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    
    meta = {
        "name": file_basename,
        "epsg": str(detected_epsg) if detected_epsg else None,
        "bounds": {
            "west": bounds.left,
            "south": bounds.bottom,
            "east": bounds.right,
            "north": bounds.top
        },
        "valueMin": data_min,
        "valueMax": data_max,
        "type": ArrayTypeMapper.to_frontend_type(array_type)
    }

    try:
        with open(output_json, "w") as f:
            json.dump(meta, f, indent=4)
        print(f"  - Saved Metadata: {output_json}")
    except Exception as e:
        return {"success": False, "error": f"Failed to save JSON: {e}"}

    # Success - return result
    return {"success": True, "filename": output_png, "basename": file_basename}


