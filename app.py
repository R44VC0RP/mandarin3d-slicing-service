from flask import Flask, request, jsonify
import threading
import os
from dotenv import load_dotenv
import printslicer as ps
import logging
import gc
import time
import requests
import tempfile
from werkzeug.utils import secure_filename
import trimesh
import pymeshlab

from logging.config import dictConfig

version = open("version", "r").read().strip()

# Enhanced logging configuration for Docker containers
dictConfig({
    'version': 1,
    'formatters': {
        'detailed': {
            'format': 'V' + version + ' - [%(asctime)s] %(levelname)s in %(module)s:%(funcName)s:%(lineno)d: %(message)s',
            'datefmt': '%Y-%m-%d %H:%M:%S'
        },
        'simple': {
            'format': 'V' + version + ' - [%(asctime)s] %(levelname)s: %(message)s',
            'datefmt': '%Y-%m-%d %H:%M:%S'
        }
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'stream': 'ext://sys.stdout',
            'formatter': 'detailed',
            'level': 'INFO'
        },
        'error_console': {
            'class': 'logging.StreamHandler', 
            'stream': 'ext://sys.stderr',
            'formatter': 'detailed',
            'level': 'ERROR'
        }
    },
    'loggers': {
        'werkzeug': {
            'level': 'INFO',
            'handlers': ['console']
        },
        'gunicorn': {
            'level': 'INFO',
            'handlers': ['console']
        }
    },
    'root': {
        'level': 'INFO',
        'handlers': ['console', 'error_console']
    },
    'disable_existing_loggers': False
})


# Load environment variables if .env file exists
load_dotenv()

# Log startup information for Docker debugging
logging.info(f"[STARTUP] ===== APPLICATION STARTING =====")
logging.info(f"[STARTUP] Version: {version}")
logging.info(f"[STARTUP] Python version: {os.sys.version}")
logging.info(f"[STARTUP] Working directory: {os.getcwd()}")
logging.info(f"[STARTUP] Environment variables loaded: {bool(os.getenv('FLASK_ENV'))}")
logging.info(f"[STARTUP] Flask environment: {os.getenv('FLASK_ENV', 'not set')}")
logging.info(f"[STARTUP] Port: {os.getenv('PORT', '80')}")


app = Flask(__name__)

tmp_directory = 'tmp'
# check if the tmp directory exists
logging.info(f"[STARTUP] Checking tmp directory: {tmp_directory}")
if not os.path.exists(tmp_directory):
    logging.info(f"[STARTUP] Creating tmp directory: {tmp_directory}")
    os.makedirs(tmp_directory)
    logging.info(f"[STARTUP] Tmp directory created successfully")
else:
    logging.info(f"[STARTUP] Tmp directory already exists")

# Log directory contents for debugging
try:
    dir_contents = os.listdir('.')
    logging.info(f"[STARTUP] Current directory contents: {dir_contents[:10]}{'...' if len(dir_contents) > 10 else ''}")
except Exception as e:
    logging.warning(f"[STARTUP] Could not list directory contents: {e}")



def download_file_from_url(url, download_path='tmp', filename=None):
    """Download a file from URL to local temp directory"""
    logging.info(f"[DOWNLOAD] Starting file download from URL: {url}")
    logging.info(f"[DOWNLOAD] Download path: {download_path}, Filename: {filename}")
    
    start_time = time.time()
    
    try:
        logging.info(f"[DOWNLOAD] Creating download directory: {download_path}")
        os.makedirs(download_path, exist_ok=True)
        
        if filename is None:
            filename = os.path.basename(url.split('?')[0])  # Remove query parameters
            logging.info(f"[DOWNLOAD] Extracted filename from URL: {filename}")
        
        # Don't force .stl extension anymore since we support multiple formats
        if not filename or '.' not in filename:
            filename = f"download_{int(time.time())}.unknown"
            logging.warning(f"[DOWNLOAD] No valid filename, using generated name: {filename}")
            
        download_path_full = os.path.join(download_path, filename)
        logging.info(f"[DOWNLOAD] Full download path: {download_path_full}")
        
        logging.info(f"[DOWNLOAD] Initiating HTTP request to: {url}")
        response = requests.get(url, stream=True)
        logging.info(f"[DOWNLOAD] HTTP response status: {response.status_code}")
        
        if response.status_code == 200:
            total_bytes = 0
            logging.info(f"[DOWNLOAD] Starting file write to: {download_path_full}")
            with open(download_path_full, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
                    total_bytes += len(chunk)
            
            download_time = time.time() - start_time
            logging.info(f"[DOWNLOAD] Successfully downloaded {total_bytes} bytes in {download_time:.2f} seconds")
            logging.info(f"[DOWNLOAD] File saved to: {download_path_full}")
            return download_path_full
        else:
            logging.error(f"[DOWNLOAD] Failed to download file from {url}. Status code: {response.status_code}")
            logging.error(f"[DOWNLOAD] Response headers: {dict(response.headers)}")
            return None
    except Exception as e:
        download_time = time.time() - start_time
        logging.error(f"[DOWNLOAD] Exception occurred after {download_time:.2f} seconds: {str(e)}")
        logging.error(f"[DOWNLOAD] Exception type: {type(e).__name__}")
        return None

def send_callback(callback_url, result_data):
    """Send results to callback URL"""
    logging.info(f"[CALLBACK] Starting callback to: {callback_url}")
    logging.info(f"[CALLBACK] Payload keys: {list(result_data.keys())}")
    logging.info(f"[CALLBACK] Result status: {result_data.get('status', 'unknown')}")
    
    start_time = time.time()
    
    try:
        logging.info(f"[CALLBACK] Sending POST request with {len(str(result_data))} bytes of data")
        response = requests.post(callback_url, json=result_data, timeout=30)
        
        callback_time = time.time() - start_time
        logging.info(f"[CALLBACK] Received response in {callback_time:.2f} seconds")
        logging.info(f"[CALLBACK] Response status code: {response.status_code}")
        
        if response.status_code == 200:
            logging.info(f"[CALLBACK] Successfully sent callback to {callback_url}")
            return True
        else:
            logging.error(f"[CALLBACK] Failed with status {response.status_code}")
            logging.error(f"[CALLBACK] Response text: {response.text[:500]}...")  # Truncate long responses
            logging.error(f"[CALLBACK] Response headers: {dict(response.headers)}")
            return False
    except requests.exceptions.Timeout:
        logging.error(f"[CALLBACK] Request timed out after 30 seconds to {callback_url}")
        return False
    except requests.exceptions.ConnectionError as e:
        logging.error(f"[CALLBACK] Connection error to {callback_url}: {str(e)}")
        return False
    except Exception as e:
        callback_time = time.time() - start_time
        logging.error(f"[CALLBACK] Exception after {callback_time:.2f} seconds: {str(e)}")
        logging.error(f"[CALLBACK] Exception type: {type(e).__name__}")
        return False

def get_file_extension(filename):
    """Get file extension in lowercase"""
    logging.debug(f"[FILE_EXT] Getting extension for filename: {filename}")
    extension = os.path.splitext(filename.lower())[1]
    logging.debug(f"[FILE_EXT] Extracted extension: {extension}")
    return extension

def is_supported_format(filename):
    """Check if file format is supported"""
    logging.debug(f"[FORMAT_CHECK] Checking format support for: {filename}")
    
    supported_formats = {
        '.stl', '.obj', '.ply', '.off', '.3mf', '.dae', '.gltf', '.glb',
        '.x3d', '.wrl', '.vrml', '.step', '.stp', '.iges', '.igs',
        '.collada', '.blend'  # Note: STEP/IGES may need special handling
    }
    
    extension = get_file_extension(filename)
    is_supported = extension in supported_formats
    
    logging.debug(f"[FORMAT_CHECK] Extension '{extension}' is {'supported' if is_supported else 'NOT supported'}")
    if not is_supported:
        logging.info(f"[FORMAT_CHECK] Supported formats: {sorted(supported_formats)}")
    
    return is_supported

def convert_to_stl_trimesh(input_path, output_path):
    """Convert 3D file to STL using trimesh"""
    logging.info(f"[CONVERT_TRIMESH] Starting conversion: {input_path} -> {output_path}")
    
    start_time = time.time()
    
    try:
        # Check input file exists and size
        if not os.path.exists(input_path):
            raise FileNotFoundError(f"Input file does not exist: {input_path}")
        
        file_size = os.path.getsize(input_path)
        logging.info(f"[CONVERT_TRIMESH] Input file size: {file_size} bytes")
        
        # Load mesh with trimesh
        logging.info(f"[CONVERT_TRIMESH] Loading mesh with trimesh...")
        mesh = trimesh.load(input_path)
        logging.info(f"[CONVERT_TRIMESH] Mesh loaded successfully, type: {type(mesh).__name__}")
        
        # Handle scene objects (for formats like GLTF, OBJ with multiple objects)
        if hasattr(mesh, 'geometry'):
            logging.info(f"[CONVERT_TRIMESH] Scene detected with {len(mesh.geometry)} geometries")
            
            # It's a Scene, combine all geometries
            if len(mesh.geometry) == 0:
                raise ValueError("No geometry found in the file")
            elif len(mesh.geometry) == 1:
                logging.info(f"[CONVERT_TRIMESH] Single geometry in scene, extracting...")
                mesh = list(mesh.geometry.values())[0]
            else:
                logging.info(f"[CONVERT_TRIMESH] Multiple geometries found, combining {len(mesh.geometry)} meshes...")
                # Combine multiple geometries
                meshes = list(mesh.geometry.values())
                mesh = trimesh.util.concatenate(meshes)
                logging.info(f"[CONVERT_TRIMESH] Meshes combined successfully")
        else:
            logging.info(f"[CONVERT_TRIMESH] Single mesh object loaded")
        
        # Ensure it's a valid mesh
        if not hasattr(mesh, 'vertices') or len(mesh.vertices) == 0:
            raise ValueError("Invalid or empty mesh")
        
        logging.info(f"[CONVERT_TRIMESH] Mesh info: {len(mesh.vertices)} vertices, {len(mesh.faces)} faces")
        
        # Fix mesh issues
        logging.info(f"[CONVERT_TRIMESH] Cleaning mesh: removing duplicate faces...")
        mesh.remove_duplicate_faces()
        
        logging.info(f"[CONVERT_TRIMESH] Cleaning mesh: removing degenerate faces...")
        mesh.remove_degenerate_faces()
        
        logging.info(f"[CONVERT_TRIMESH] Cleaning mesh: filling holes...")
        mesh.fill_holes()
        
        logging.info(f"[CONVERT_TRIMESH] Final mesh: {len(mesh.vertices)} vertices, {len(mesh.faces)} faces")
        
        # Export as STL
        logging.info(f"[CONVERT_TRIMESH] Exporting to STL: {output_path}")
        mesh.export(output_path)
        
        # Verify output file was created
        if os.path.exists(output_path):
            output_size = os.path.getsize(output_path)
            conversion_time = time.time() - start_time
            logging.info(f"[CONVERT_TRIMESH] Conversion successful in {conversion_time:.2f}s")
            logging.info(f"[CONVERT_TRIMESH] Output file size: {output_size} bytes")
            return True
        else:
            raise Exception("Output file was not created")
        
    except Exception as e:
        conversion_time = time.time() - start_time
        logging.error(f"[CONVERT_TRIMESH] Conversion failed after {conversion_time:.2f}s: {str(e)}")
        logging.error(f"[CONVERT_TRIMESH] Exception type: {type(e).__name__}")
        return False

def convert_to_stl_pymeshlab(input_path, output_path):
    """Convert 3D file to STL using PyMeshLab (fallback for STEP/complex formats)"""
    logging.info(f"[CONVERT_PYMESHLAB] Starting conversion: {input_path} -> {output_path}")
    
    start_time = time.time()
    
    try:
        # Check input file exists and size
        if not os.path.exists(input_path):
            raise FileNotFoundError(f"Input file does not exist: {input_path}")
        
        file_size = os.path.getsize(input_path)
        logging.info(f"[CONVERT_PYMESHLAB] Input file size: {file_size} bytes")
        
        logging.info(f"[CONVERT_PYMESHLAB] Initializing PyMeshLab MeshSet...")
        ms = pymeshlab.MeshSet()
        
        logging.info(f"[CONVERT_PYMESHLAB] Loading mesh from: {input_path}")
        ms.load_new_mesh(input_path)
        
        current_mesh = ms.current_mesh()
        vertex_count = current_mesh.vertex_number()
        face_count = current_mesh.face_number()
        
        logging.info(f"[CONVERT_PYMESHLAB] Loaded mesh: {vertex_count} vertices, {face_count} faces")
        
        # Apply some basic cleaning
        if vertex_count > 0:
            logging.info(f"[CONVERT_PYMESHLAB] Cleaning mesh: removing duplicate vertices...")
            ms.meshing_remove_duplicate_vertices()
            
            logging.info(f"[CONVERT_PYMESHLAB] Cleaning mesh: removing duplicate faces...")
            ms.meshing_remove_duplicate_faces()
            
            logging.info(f"[CONVERT_PYMESHLAB] Cleaning mesh: filling holes (max size: 30)...")
            ms.meshing_close_holes(maxholesize=30)
            
            # Log final mesh stats
            final_mesh = ms.current_mesh()
            final_vertices = final_mesh.vertex_number()
            final_faces = final_mesh.face_number()
            logging.info(f"[CONVERT_PYMESHLAB] Final mesh: {final_vertices} vertices, {final_faces} faces")
        else:
            logging.warning(f"[CONVERT_PYMESHLAB] Mesh has no vertices, skipping cleanup")
        
        # Save as STL
        logging.info(f"[CONVERT_PYMESHLAB] Saving mesh as STL: {output_path}")
        ms.save_current_mesh(output_path)
        
        # Verify output file was created
        if os.path.exists(output_path):
            output_size = os.path.getsize(output_path)
            conversion_time = time.time() - start_time
            logging.info(f"[CONVERT_PYMESHLAB] Conversion successful in {conversion_time:.2f}s")
            logging.info(f"[CONVERT_PYMESHLAB] Output file size: {output_size} bytes")
            return True
        else:
            raise Exception("Output file was not created")
        
    except Exception as e:
        conversion_time = time.time() - start_time
        logging.error(f"[CONVERT_PYMESHLAB] Conversion failed after {conversion_time:.2f}s: {str(e)}")
        logging.error(f"[CONVERT_PYMESHLAB] Exception type: {type(e).__name__}")
        return False

def convert_file_to_stl(input_path, file_id=None):
    """Convert various 3D file formats to STL"""
    logging.info(f"[CONVERT_STL] Starting conversion process for: {input_path}")
    logging.info(f"[CONVERT_STL] File ID: {file_id}")
    
    start_time = time.time()
    
    # Check if input file exists
    if not os.path.exists(input_path):
        logging.error(f"[CONVERT_STL] Input file does not exist: {input_path}")
        return None
    
    file_ext = get_file_extension(input_path)
    logging.info(f"[CONVERT_STL] Detected file extension: {file_ext}")
    
    # If already STL, return as-is
    if file_ext == '.stl':
        logging.info(f"[CONVERT_STL] File is already STL format, no conversion needed")
        return input_path
    
    # Generate output STL path
    base_name = os.path.splitext(os.path.basename(input_path))[0]
    output_filename = f"{file_id or base_name}_{int(time.time())}_converted.stl"
    output_path = os.path.join(tmp_directory, output_filename)
    
    logging.info(f"[CONVERT_STL] Converting {file_ext} to STL: {input_path} -> {output_path}")
    logging.info(f"[CONVERT_STL] Generated output filename: {output_filename}")
    
    # Try trimesh first (works for most formats)
    logging.info(f"[CONVERT_STL] Attempting conversion with trimesh (primary method)...")
    if convert_to_stl_trimesh(input_path, output_path):
        logging.info(f"[CONVERT_STL] Trimesh conversion successful, cleaning up original file...")
        # Clean up original file
        try:
            os.remove(input_path)
            logging.info(f"[CONVERT_STL] Original file removed: {input_path}")
        except Exception as e:
            logging.warning(f"[CONVERT_STL] Could not remove original file {input_path}: {e}")
        
        conversion_time = time.time() - start_time
        logging.info(f"[CONVERT_STL] Total conversion completed in {conversion_time:.2f}s")
        return output_path
    
    # Fallback to PyMeshLab for complex formats
    logging.info(f"[CONVERT_STL] Trimesh conversion failed, trying PyMeshLab (fallback method)...")
    if convert_to_stl_pymeshlab(input_path, output_path):
        logging.info(f"[CONVERT_STL] PyMeshLab conversion successful, cleaning up original file...")
        # Clean up original file
        try:
            os.remove(input_path)
            logging.info(f"[CONVERT_STL] Original file removed: {input_path}")
        except Exception as e:
            logging.warning(f"[CONVERT_STL] Could not remove original file {input_path}: {e}")
        
        conversion_time = time.time() - start_time
        logging.info(f"[CONVERT_STL] Total conversion completed in {conversion_time:.2f}s")
        return output_path
    
    # Both methods failed
    conversion_time = time.time() - start_time
    logging.error(f"[CONVERT_STL] All conversion methods failed after {conversion_time:.2f}s")
    logging.error(f"[CONVERT_STL] Failed to convert {input_path} to STL using all available methods")
    logging.error(f"[CONVERT_STL] Attempted methods: trimesh, pymeshlab")
    return None

def process_3d_file(file_path, callback_url, file_id=None, max_dimensions=None):
    """Process 3D file (convert if needed) and send results to callback URL"""
    logging.info(f"[PROCESS] ===== STARTING 3D FILE PROCESSING =====")
    logging.info(f"[PROCESS] File path: {file_path}")
    logging.info(f"[PROCESS] Callback URL: {callback_url}")
    logging.info(f"[PROCESS] File ID: {file_id}")
    logging.info(f"[PROCESS] Max dimensions: {max_dimensions}")
    
    start_time = time.time()
    
    # Set default max dimensions if not provided
    if max_dimensions is None:
        max_dimensions = {'x': 300, 'y': 300, 'z': 300}
        logging.info(f"[PROCESS] Using default max dimensions: {max_dimensions}")
    
    # Log system information for Docker debugging
    logging.info(f"[PROCESS] Current working directory: {os.getcwd()}")
    logging.info(f"[PROCESS] Temp directory: {tmp_directory}")
    logging.info(f"[PROCESS] Python version: {os.sys.version}")
    
    # Check if input file exists and get info
    if os.path.exists(file_path):
        file_size = os.path.getsize(file_path)
        logging.info(f"[PROCESS] Input file exists, size: {file_size} bytes")
    else:
        logging.error(f"[PROCESS] Input file does not exist: {file_path}")
    
    try:
        logging.info(f"[PROCESS] Starting 3D file processing for file: {file_path}")
        
        # Convert to STL if not already STL
        logging.info(f"[PROCESS] Step 1: Converting file to STL format...")
        conversion_start_time = time.time()
        stl_path = convert_file_to_stl(file_path, file_id)
        conversion_time = time.time() - conversion_start_time
        
        if not stl_path:
            logging.error(f"[PROCESS] Conversion failed after {conversion_time:.2f}s")
            error_data = {
                "file_id": file_id,
                "status": "error",
                "error": "Failed to convert file to STL format",
                "processing_time": time.time() - start_time,
                "conversion_time": conversion_time,
                "timestamp": time.time()
            }
            logging.info(f"[PROCESS] Sending error callback for conversion failure...")
            send_callback(callback_url, error_data)
            return error_data
        
        logging.info(f"[PROCESS] Conversion completed in {conversion_time:.2f}s. STL path: {stl_path}")
        
        # Get absolute path
        absolute_path = os.path.abspath(stl_path)
        logging.info(f"[PROCESS] Absolute STL path: {absolute_path}")
        
        # Verify STL file was created properly
        if os.path.exists(absolute_path):
            stl_size = os.path.getsize(absolute_path)
            logging.info(f"[PROCESS] STL file verified, size: {stl_size} bytes")
        else:
            logging.error(f"[PROCESS] STL file was not created: {absolute_path}")
        
        # Run slicer to get mass and dimensions
        logging.info(f"[PROCESS] Step 2: Running slicer analysis...")
        slicer_start_time = time.time()
        response = ps.run_slicer_command_and_extract_info(absolute_path, os.path.basename(file_path))
        slicer_end_time = time.time()
        
        processing_time = slicer_end_time - start_time
        slicer_time = slicer_end_time - slicer_start_time
        
        logging.info(f"[PROCESS] Slicer analysis completed in {slicer_time:.2f}s")
        logging.info(f"[PROCESS] Slicer response status: {response.get('status', 'unknown')}")
        
        if 'mass' in response:
            logging.info(f"[PROCESS] Extracted mass: {response['mass']:.2f}g")
        if 'size_x' in response and 'size_y' in response and 'size_z' in response:
            logging.info(f"[PROCESS] Extracted dimensions: {response['size_x']:.2f}x{response['size_y']:.2f}x{response['size_z']:.2f}mm")
        
        # Clean up temporary file
        logging.info(f"[PROCESS] Step 3: Cleaning up temporary files...")
        try:
            os.remove(absolute_path)
            logging.info(f"[PROCESS] Temporary STL file removed: {absolute_path}")
        except Exception as e:
            logging.warning(f"[PROCESS] Failed to clean up temp file {absolute_path}: {e}")
        
        # Prepare result data
        result_data = {
            "file_id": file_id,
            "processing_time": processing_time,
            "conversion_time": conversion_time,
            "slicer_time": slicer_time,
            "timestamp": time.time()
        }
        
        if response['status'] == 200:
            logging.info(f"[PROCESS] Step 4: Validating dimensions against limits...")
            logging.info(f"[PROCESS] Model dimensions: {response['size_x']:.2f}x{response['size_y']:.2f}x{response['size_z']:.2f}mm")
            logging.info(f"[PROCESS] Max allowed: {max_dimensions['x']}x{max_dimensions['y']}x{max_dimensions['z']}mm")
            
            # Check dimensions
            if (response['size_x'] > max_dimensions['x'] or 
                response['size_y'] > max_dimensions['y'] or 
                response['size_z'] > max_dimensions['z']):
                
                # Find which dimension is too large
                dimension = 'X' if response['size_x'] > max_dimensions['x'] else \
                           'Y' if response['size_y'] > max_dimensions['y'] else 'Z'
                
                logging.warning(f"[PROCESS] Dimension validation failed: {dimension} dimension too large")
                
                result_data.update({
                    "status": "error",
                    "error": f"Dimension {dimension} too large. Model dimensions: {response['size_x']:.2f}x{response['size_y']:.2f}x{response['size_z']:.2f}mm. Max allowed: {max_dimensions['x']}x{max_dimensions['y']}x{max_dimensions['z']}mm.",
                    "dimensions": {
                        "x": response['size_x'],
                        "y": response['size_y'], 
                        "z": response['size_z']
                    }
                })
            else:
                logging.info(f"[PROCESS] Dimension validation passed - model fits within limits")
                result_data.update({
                    "status": "success",
                    "mass_grams": response['mass'],
                    "dimensions": {
                        "x": response['size_x'],
                        "y": response['size_y'],
                        "z": response['size_z']
                    }
                })
        else:
            logging.error(f"[PROCESS] Slicer analysis failed with status {response['status']}")
            result_data.update({
                "status": "error",
                "error": response.get('error', 'Unknown slicing error')
            })
        
        # Send callback
        logging.info(f"[PROCESS] Step 5: Sending results via callback...")
        callback_success = send_callback(callback_url, result_data)
        
        logging.info(f"[PROCESS] ===== PROCESSING COMPLETED =====")
        logging.info(f"[PROCESS] Final status: {result_data['status']}")
        logging.info(f"[PROCESS] Total processing time: {processing_time:.2f}s")
        logging.info(f"[PROCESS] Callback sent: {callback_success}")
        
        return result_data
        
    except Exception as e:
        processing_time = time.time() - start_time
        logging.error(f"[PROCESS] ===== PROCESSING FAILED =====")
        logging.error(f"[PROCESS] Exception after {processing_time:.2f}s: {str(e)}")
        logging.error(f"[PROCESS] Exception type: {type(e).__name__}")
        logging.error(f"[PROCESS] File path: {file_path}")
        
        error_data = {
            "file_id": file_id,
            "status": "error", 
            "error": f"Processing error: {str(e)}",
            "processing_time": processing_time,
            "timestamp": time.time()
        }
        
        logging.info(f"[PROCESS] Sending error callback...")
        send_callback(callback_url, error_data)
        return error_data


@app.route('/api/slice', methods=['POST'])
def slice_3d_file():
    """
    Process 3D file (STL, OBJ, 3MF, STEP, etc.) and return results via callback
    
    Supported formats: STL, OBJ, PLY, OFF, 3MF, GLTF, GLB, DAE, X3D, WRL, VRML, 
                      STEP, STP, IGES, IGS, COLLADA, BLEND
    
    Request body can be:
    1. JSON with file URL:
    {
        "file_url": "https://example.com/model.obj",
        "callback_url": "https://your-api.com/callback",
        "file_id": "optional_file_identifier",
        "file_name": "model.stl",  // optional: use when URL lacks filename/extension
        "max_dimensions": {"x": 300, "y": 300, "z": 300}  // optional
    }
    
    2. Form-data with file upload:
    - model_file: 3D model file (STL, OBJ, 3MF, STEP, etc.)
    - callback_url: callback URL
    - file_id: optional file identifier 
    - max_x, max_y, max_z: optional dimension limits
    """
    request_start_time = time.time()
    logging.info(f"[API] ##### NEW API REQUEST TO /api/slice #####")
    logging.info(f"[API] Request method: {request.method}")
    logging.info(f"[API] Request content type: {request.content_type}")
    logging.info(f"[API] Request is_json: {request.is_json}")
    logging.info(f"[API] Request remote_addr: {request.remote_addr}")
    logging.info(f"[API] Request user_agent: {request.headers.get('User-Agent', 'Unknown')}")
    
    try:
        # Check if it's JSON request (URL) or form-data (file upload)
        if request.is_json:
            logging.info(f"[API] Processing JSON request (URL download)...")
            data = request.get_json()
            logging.info(f"[API] JSON keys received: {list(data.keys())}")
            
            file_url = data.get('file_url') or data.get('stl_url')  # Support old parameter name
            callback_url = data.get('callback_url')
            file_id = data.get('file_id')
            provided_file_name = data.get('file_name')  # Optional filename when URL lacks it
            max_dimensions = data.get('max_dimensions', {'x': 300, 'y': 300, 'z': 300})
            
            logging.info(f"[API] File URL: {file_url}")
            logging.info(f"[API] Callback URL: {callback_url}")
            logging.info(f"[API] File ID: {file_id}")
            logging.info(f"[API] Provided filename: {provided_file_name}")
            logging.info(f"[API] Max dimensions: {max_dimensions}")
            
            if not file_url or not callback_url:
                logging.error(f"[API] Missing required parameters - file_url: {bool(file_url)}, callback_url: {bool(callback_url)}")
                return jsonify({"error": "file_url and callback_url are required"}), 400
            
            # Determine filename for validation and storage
            logging.info(f"[API] Determining filename for validation...")
            if provided_file_name:
                # Use provided filename (for URLs without filename/extension)
                original_filename = provided_file_name
                logging.info(f"[API] Using provided filename: {original_filename}")
            else:
                # Extract original filename and extension from URL
                original_filename = os.path.basename(file_url.split('?')[0])  # Remove query params
                logging.info(f"[API] Extracted filename from URL: {original_filename}")
                if not original_filename or '.' not in original_filename:
                    logging.error(f"[API] URL does not contain valid filename: {file_url}")
                    return jsonify({
                        "error": "URL does not contain a filename with extension. Please provide a 'file_name' parameter with the correct filename and extension."
                    }), 400
            
            # Check if format is supported
            logging.info(f"[API] Checking if format is supported for: {original_filename}")
            if not is_supported_format(original_filename):
                logging.error(f"[API] Unsupported file format: {get_file_extension(original_filename)}")
                return jsonify({
                    "error": f"Unsupported file format. Supported formats: STL, OBJ, PLY, OFF, 3MF, GLTF, GLB, DAE, X3D, WRL, VRML, STEP, STP, IGES, IGS, COLLADA, BLEND"
                }), 400
            
            # Download file from URL
            filename = f"{file_id or 'temp'}_{int(time.time())}_{original_filename}"
            logging.info(f"[API] Generated filename for download: {filename}")
            
            download_start_time = time.time()
            file_path = download_file_from_url(file_url, tmp_directory, filename)
            download_time = time.time() - download_start_time
            
            if not file_path:
                logging.error(f"[API] File download failed after {download_time:.2f}s")
                error_data = {
                    "file_id": file_id,
                    "status": "error",
                    "error": "Failed to download 3D file from URL",
                    "download_time": download_time,
                    "timestamp": time.time()
                }
                send_callback(callback_url, error_data)
                return jsonify({"error": "Failed to download 3D file"}), 400
                
            logging.info(f"[API] File downloaded successfully in {download_time:.2f}s: {file_path}")
                
        else:
            logging.info(f"[API] Processing form-data request (file upload)...")
            logging.info(f"[API] Form keys: {list(request.form.keys())}")
            logging.info(f"[API] File keys: {list(request.files.keys())}")
            
            # Handle file upload - check multiple possible field names
            file = None
            used_field_name = None
            for field_name in ['model_file', 'stl_file', '3d_file', 'file']:
                if field_name in request.files:
                    file = request.files[field_name]
                    used_field_name = field_name
                    logging.info(f"[API] Found file in field: {field_name}")
                    break
            
            if not file:
                logging.error(f"[API] No file found in any expected field names")
                return jsonify({"error": "No 3D model file provided. Use 'model_file' field name."}), 400
            
            callback_url = request.form.get('callback_url')
            file_id = request.form.get('file_id')
            
            logging.info(f"[API] Callback URL: {callback_url}")
            logging.info(f"[API] File ID: {file_id}")
            logging.info(f"[API] Uploaded filename: {file.filename}")
            
            if not callback_url:
                logging.error(f"[API] Missing callback_url in form data")
                return jsonify({"error": "callback_url is required"}), 400
            
            if file.filename == '':
                logging.error(f"[API] Empty filename provided")
                return jsonify({"error": "No file selected"}), 400
            
            # Check if format is supported
            logging.info(f"[API] Checking format support for uploaded file: {file.filename}")
            if not is_supported_format(file.filename):
                logging.error(f"[API] Unsupported format: {get_file_extension(file.filename)}")
                return jsonify({
                    "error": f"Unsupported file format. Supported formats: STL, OBJ, PLY, OFF, 3MF, GLTF, GLB, DAE, X3D, WRL, VRML, STEP, STP, IGES, IGS, COLLADA, BLEND"
                }), 400
            
            # Save uploaded file
            filename = secure_filename(f"{file_id or 'upload'}_{int(time.time())}_{file.filename}")
            file_path = os.path.join(tmp_directory, filename)
            
            logging.info(f"[API] Saving uploaded file to: {file_path}")
            upload_start_time = time.time()
            file.save(file_path)
            upload_time = time.time() - upload_start_time
            
            # Verify file was saved and get size
            if os.path.exists(file_path):
                uploaded_size = os.path.getsize(file_path)
                logging.info(f"[API] File saved successfully in {upload_time:.2f}s, size: {uploaded_size} bytes")
            else:
                logging.error(f"[API] File was not saved to {file_path}")
            
            # Get max dimensions from form data
            max_dimensions = {
                'x': float(request.form.get('max_x', 300)),
                'y': float(request.form.get('max_y', 300)),
                'z': float(request.form.get('max_z', 300))
            }
            logging.info(f"[API] Max dimensions from form: {max_dimensions}")
        
        # Start processing in background thread
        request_time = time.time() - request_start_time
        logging.info(f"[API] Request processing completed in {request_time:.2f}s, starting background thread...")
        
        def process_async():
            with app.app_context():
                logging.info(f"[API] Background thread started for file processing")
                process_3d_file(file_path, callback_url, file_id, max_dimensions)
                logging.info(f"[API] Background processing completed, running garbage collection")
                gc.collect()
        
        thread = threading.Thread(target=process_async)
        thread.start()
        
        response_data = {
            "message": "3D file processing started", 
            "file_id": file_id,
            "status": "processing",
            "original_format": get_file_extension(filename).upper().replace('.', '') if filename else "unknown",
            "request_processing_time": request_time
        }
        
        logging.info(f"[API] Returning 202 response: {response_data}")
        logging.info(f"[API] ##### API REQUEST COMPLETED #####")
        
        return jsonify(response_data), 202
        
    except Exception as e:
        request_time = time.time() - request_start_time
        logging.error(f"[API] ##### API REQUEST FAILED #####")
        logging.error(f"[API] Exception after {request_time:.2f}s: {str(e)}")
        logging.error(f"[API] Exception type: {type(e).__name__}")
        logging.error(f"[API] Request method: {request.method}")
        logging.error(f"[API] Content type: {request.content_type}")
        return jsonify({
            "error": f"Internal server error: {str(e)}",
            "request_processing_time": request_time
        }), 500

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    logging.info(f"[HEALTH] Health check requested from {request.remote_addr}")
    
    # Basic system checks
    health_status = {
        "status": "healthy",
        "version": version,
        "timestamp": time.time(),
        "supported_formats": ["STL", "OBJ", "PLY", "OFF", "3MF", "GLTF", "GLB", "DAE", "X3D", "WRL", "VRML", "STEP", "STP", "IGES", "IGS", "COLLADA", "BLEND"]
    }
    
    # Add system info for Docker debugging
    health_status.update({
        "system_info": {
            "working_directory": os.getcwd(),
            "tmp_directory_exists": os.path.exists(tmp_directory),
            "superslicer_exists": os.path.exists('./slicersuper'),
            "config_exists": os.path.exists('config.ini'),
            "python_version": os.sys.version.split()[0]
        }
    })
    
    logging.info(f"[HEALTH] Health check completed: {health_status['status']}")
    return jsonify(health_status), 200

@app.route('/api/formats', methods=['GET'])
def supported_formats():
    """Get list of supported 3D file formats"""
    formats = {
        "supported_formats": [
            {"extension": "STL", "description": "Stereolithography", "native": True},
            {"extension": "OBJ", "description": "Wavefront OBJ", "native": False},
            {"extension": "PLY", "description": "Polygon File Format", "native": False},
            {"extension": "OFF", "description": "Object File Format", "native": False},
            {"extension": "3MF", "description": "3D Manufacturing Format", "native": False},
            {"extension": "GLTF", "description": "GL Transmission Format", "native": False},
            {"extension": "GLB", "description": "GL Transmission Format Binary", "native": False},
            {"extension": "DAE", "description": "COLLADA Digital Asset Exchange", "native": False},
            {"extension": "X3D", "description": "Extensible 3D", "native": False},
            {"extension": "WRL", "description": "VRML World", "native": False},
            {"extension": "VRML", "description": "Virtual Reality Modeling Language", "native": False},
            {"extension": "STEP", "description": "Standard for Exchange of Product Data", "native": False},
            {"extension": "STP", "description": "STEP File", "native": False},
            {"extension": "IGES", "description": "Initial Graphics Exchange Specification", "native": False},
            {"extension": "IGS", "description": "IGES File", "native": False},
            {"extension": "COLLADA", "description": "COLLAborative Design Activity", "native": False},
            {"extension": "BLEND", "description": "Blender File", "native": False}
        ],
        "conversion_info": {
            "primary_engine": "trimesh",
            "fallback_engine": "pymeshlab",
            "note": "Files are automatically converted to STL before slicing. Native STL files are processed directly."
        }
    }
    return jsonify(formats), 200


# run app so it can be run with flask
if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5030, debug=True)

