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

dictConfig({
    'version': 1,
    'formatters': {'default': {
        'format': 'V' + version + ' - [%(asctime)s] %(levelname)s in %(module)s: %(message)s',
    }},
    'handlers': {'wsgi': {
        'class': 'logging.StreamHandler',
        'stream': 'ext://sys.stdout',  # Use 'ext://sys.stderr' for stderr
        'formatter': 'default'
    }},
    'root': {
        'level': 'INFO',
        'handlers': ['wsgi']
    }
})


# Load environment variables if .env file exists
load_dotenv()


app = Flask(__name__)

tmp_directory = 'tmp'
# check if the tmp directory exists
if not os.path.exists(tmp_directory):
    os.makedirs(tmp_directory)



def download_file_from_url(url, download_path='tmp', filename=None):
    """Download a file from URL to local temp directory"""
    try:
        os.makedirs(download_path, exist_ok=True)
        
        if filename is None:
            filename = os.path.basename(url.split('?')[0])  # Remove query parameters
        
        # Don't force .stl extension anymore since we support multiple formats
        if not filename or '.' not in filename:
            filename = f"download_{int(time.time())}.unknown"
            
        download_path_full = os.path.join(download_path, filename)
        
        response = requests.get(url, stream=True)
        if response.status_code == 200:
            with open(download_path_full, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            return download_path_full
        else:
            logging.error(f"Failed to download file from {url}. Status code: {response.status_code}")
            return None
    except Exception as e:
        logging.error(f"An error occurred while downloading the file: {e}")
        return None

def send_callback(callback_url, result_data):
    """Send results to callback URL"""
    try:
        response = requests.post(callback_url, json=result_data, timeout=30)
        if response.status_code == 200:
            logging.info(f"Successfully sent callback to {callback_url}")
            return True
        else:
            logging.error(f"Callback failed with status {response.status_code}: {response.text}")
            return False
    except Exception as e:
        logging.error(f"Failed to send callback to {callback_url}: {str(e)}")
        return False

def get_file_extension(filename):
    """Get file extension in lowercase"""
    return os.path.splitext(filename.lower())[1]

def is_supported_format(filename):
    """Check if file format is supported"""
    supported_formats = {
        '.stl', '.obj', '.ply', '.off', '.3mf', '.dae', '.gltf', '.glb',
        '.x3d', '.wrl', '.vrml', '.step', '.stp', '.iges', '.igs',
        '.collada', '.blend'  # Note: STEP/IGES may need special handling
    }
    return get_file_extension(filename) in supported_formats

def convert_to_stl_trimesh(input_path, output_path):
    """Convert 3D file to STL using trimesh"""
    try:
        logging.info(f"Converting {input_path} to STL using trimesh")
        
        # Load mesh with trimesh
        mesh = trimesh.load(input_path)
        
        # Handle scene objects (for formats like GLTF, OBJ with multiple objects)
        if hasattr(mesh, 'geometry'):
            # It's a Scene, combine all geometries
            if len(mesh.geometry) == 0:
                raise ValueError("No geometry found in the file")
            elif len(mesh.geometry) == 1:
                mesh = list(mesh.geometry.values())[0]
            else:
                # Combine multiple geometries
                meshes = list(mesh.geometry.values())
                mesh = trimesh.util.concatenate(meshes)
        
        # Ensure it's a valid mesh
        if not hasattr(mesh, 'vertices') or len(mesh.vertices) == 0:
            raise ValueError("Invalid or empty mesh")
        
        # Fix mesh issues
        mesh.remove_duplicate_faces()
        mesh.remove_degenerate_faces()
        mesh.fill_holes()
        
        # Export as STL
        mesh.export(output_path)
        logging.info(f"Successfully converted to STL: {output_path}")
        return True
        
    except Exception as e:
        logging.error(f"Trimesh conversion failed: {str(e)}")
        return False

def convert_to_stl_pymeshlab(input_path, output_path):
    """Convert 3D file to STL using PyMeshLab (fallback for STEP/complex formats)"""
    try:
        logging.info(f"Converting {input_path} to STL using PyMeshLab")
        
        ms = pymeshlab.MeshSet()
        ms.load_new_mesh(input_path)
        
        # Apply some basic cleaning
        if ms.current_mesh().vertex_number() > 0:
            # Remove duplicate vertices
            ms.meshing_remove_duplicate_vertices()
            # Remove duplicate faces
            ms.meshing_remove_duplicate_faces()
            # Fill holes if any
            ms.meshing_close_holes(maxholesize=30)
        
        # Save as STL
        ms.save_current_mesh(output_path)
        logging.info(f"Successfully converted to STL using PyMeshLab: {output_path}")
        return True
        
    except Exception as e:
        logging.error(f"PyMeshLab conversion failed: {str(e)}")
        return False

def convert_file_to_stl(input_path, file_id=None):
    """Convert various 3D file formats to STL"""
    file_ext = get_file_extension(input_path)
    
    # If already STL, return as-is
    if file_ext == '.stl':
        return input_path
    
    # Generate output STL path
    base_name = os.path.splitext(os.path.basename(input_path))[0]
    output_filename = f"{file_id or base_name}_{int(time.time())}_converted.stl"
    output_path = os.path.join(tmp_directory, output_filename)
    
    logging.info(f"Converting {file_ext} file to STL: {input_path} -> {output_path}")
    
    # Try trimesh first (works for most formats)
    if convert_to_stl_trimesh(input_path, output_path):
        # Clean up original file
        try:
            os.remove(input_path)
        except Exception as e:
            logging.warning(f"Could not remove original file {input_path}: {e}")
        return output_path
    
    # Fallback to PyMeshLab for complex formats
    logging.info("Trimesh conversion failed, trying PyMeshLab...")
    if convert_to_stl_pymeshlab(input_path, output_path):
        # Clean up original file
        try:
            os.remove(input_path)
        except Exception as e:
            logging.warning(f"Could not remove original file {input_path}: {e}")
        return output_path
    
    # Both methods failed
    logging.error(f"Failed to convert {input_path} to STL using all available methods")
    return None

def process_3d_file(file_path, callback_url, file_id=None, max_dimensions=None):
    """Process 3D file (convert if needed) and send results to callback URL"""
    start_time = time.time()
    
    # Set default max dimensions if not provided
    if max_dimensions is None:
        max_dimensions = {'x': 300, 'y': 300, 'z': 300}
    
    try:
        logging.info(f"Starting 3D file processing for file: {file_path}")
        
        # Convert to STL if not already STL
        stl_path = convert_file_to_stl(file_path, file_id)
        if not stl_path:
            error_data = {
                "file_id": file_id,
                "status": "error",
                "error": "Failed to convert file to STL format",
                "processing_time": time.time() - start_time,
                "timestamp": time.time()
            }
            send_callback(callback_url, error_data)
            return error_data
        
        # Get absolute path
        absolute_path = os.path.abspath(stl_path)
        
        # Run slicer to get mass and dimensions
        slicer_start_time = time.time()
        response = ps.run_slicer_command_and_extract_info(absolute_path, os.path.basename(file_path))
        slicer_end_time = time.time()
        
        processing_time = slicer_end_time - start_time
        slicer_time = slicer_end_time - slicer_start_time
        
        # Clean up temporary file
        try:
            os.remove(absolute_path)
            logging.info(f"Cleaned up temporary file: {absolute_path}")
        except Exception as e:
            logging.warning(f"Failed to clean up temp file {absolute_path}: {e}")
        
        # Prepare result data
        result_data = {
            "file_id": file_id,
            "processing_time": processing_time,
            "slicer_time": slicer_time,
            "timestamp": time.time()
        }
        
        if response['status'] == 200:
            # Check dimensions
            if (response['size_x'] > max_dimensions['x'] or 
                response['size_y'] > max_dimensions['y'] or 
                response['size_z'] > max_dimensions['z']):
                
                # Find which dimension is too large
                dimension = 'X' if response['size_x'] > max_dimensions['x'] else \
                           'Y' if response['size_y'] > max_dimensions['y'] else 'Z'
                
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
            result_data.update({
                "status": "error",
                "error": response.get('error', 'Unknown slicing error')
            })
        
        # Send callback
        callback_success = send_callback(callback_url, result_data)
        
        logging.info(f"STL processing completed. Status: {result_data['status']}, Callback sent: {callback_success}")
        return result_data
        
    except Exception as e:
        logging.error(f"Error processing STL file {file_path}: {str(e)}")
        error_data = {
            "file_id": file_id,
            "status": "error", 
            "error": f"Processing error: {str(e)}",
            "processing_time": time.time() - start_time,
            "timestamp": time.time()
        }
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
    try:
        # Check if it's JSON request (URL) or form-data (file upload)
        if request.is_json:
            data = request.get_json()
            file_url = data.get('file_url') or data.get('stl_url')  # Support old parameter name
            callback_url = data.get('callback_url')
            file_id = data.get('file_id')
            provided_file_name = data.get('file_name')  # Optional filename when URL lacks it
            max_dimensions = data.get('max_dimensions', {'x': 300, 'y': 300, 'z': 300})
            
            if not file_url or not callback_url:
                return jsonify({"error": "file_url and callback_url are required"}), 400
            
            # Determine filename for validation and storage
            if provided_file_name:
                # Use provided filename (for URLs without filename/extension)
                original_filename = provided_file_name
            else:
                # Extract original filename and extension from URL
                original_filename = os.path.basename(file_url.split('?')[0])  # Remove query params
                if not original_filename or '.' not in original_filename:
                    return jsonify({
                        "error": "URL does not contain a filename with extension. Please provide a 'file_name' parameter with the correct filename and extension."
                    }), 400
            
            # Check if format is supported
            if not is_supported_format(original_filename):
                return jsonify({
                    "error": f"Unsupported file format. Supported formats: STL, OBJ, PLY, OFF, 3MF, GLTF, GLB, DAE, X3D, WRL, VRML, STEP, STP, IGES, IGS, COLLADA, BLEND"
                }), 400
            
            # Download file from URL
            filename = f"{file_id or 'temp'}_{int(time.time())}_{original_filename}"
            file_path = download_file_from_url(file_url, tmp_directory, filename)
            
            if not file_path:
                error_data = {
                    "file_id": file_id,
                    "status": "error",
                    "error": "Failed to download 3D file from URL",
                    "timestamp": time.time()
                }
                send_callback(callback_url, error_data)
                return jsonify({"error": "Failed to download 3D file"}), 400
                
        else:
            # Handle file upload - check multiple possible field names
            file = None
            for field_name in ['model_file', 'stl_file', '3d_file', 'file']:
                if field_name in request.files:
                    file = request.files[field_name]
                    break
            
            if not file:
                return jsonify({"error": "No 3D model file provided. Use 'model_file' field name."}), 400
            
            callback_url = request.form.get('callback_url')
            file_id = request.form.get('file_id')
            
            if not callback_url:
                return jsonify({"error": "callback_url is required"}), 400
            
            if file.filename == '':
                return jsonify({"error": "No file selected"}), 400
            
            # Check if format is supported
            if not is_supported_format(file.filename):
                return jsonify({
                    "error": f"Unsupported file format. Supported formats: STL, OBJ, PLY, OFF, 3MF, GLTF, GLB, DAE, X3D, WRL, VRML, STEP, STP, IGES, IGS, COLLADA, BLEND"
                }), 400
            
            # Save uploaded file
            filename = secure_filename(f"{file_id or 'upload'}_{int(time.time())}_{file.filename}")
            file_path = os.path.join(tmp_directory, filename)
            file.save(file_path)
            
            # Get max dimensions from form data
            max_dimensions = {
                'x': float(request.form.get('max_x', 300)),
                'y': float(request.form.get('max_y', 300)),
                'z': float(request.form.get('max_z', 300))
            }
        
        # Start processing in background thread
        def process_async():
            with app.app_context():
                process_3d_file(file_path, callback_url, file_id, max_dimensions)
                gc.collect()
        
        thread = threading.Thread(target=process_async)
        thread.start()
        
        return jsonify({
            "message": "3D file processing started", 
            "file_id": file_id,
            "status": "processing",
            "original_format": get_file_extension(filename).upper().replace('.', '') if filename else "unknown"
        }), 202
        
    except Exception as e:
        logging.error(f"Error in slice_3d_file endpoint: {str(e)}")
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "version": version,
        "timestamp": time.time(),
        "supported_formats": ["STL", "OBJ", "PLY", "OFF", "3MF", "GLTF", "GLB", "DAE", "X3D", "WRL", "VRML", "STEP", "STP", "IGES", "IGS", "COLLADA", "BLEND"]
    }), 200

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

