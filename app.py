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
            filename = os.path.basename(url)
        
        if not filename.endswith('.stl'):
            filename = f"{filename}.stl"
            
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

def process_stl_file(file_path, callback_url, file_id=None, max_dimensions=None):
    """Process STL file and send results to callback URL"""
    start_time = time.time()
    
    # Set default max dimensions if not provided
    if max_dimensions is None:
        max_dimensions = {'x': 300, 'y': 300, 'z': 300}
    
    try:
        logging.info(f"Starting STL processing for file: {file_path}")
        
        # Get absolute path
        absolute_path = os.path.abspath(file_path)
        
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
def slice_stl():
    """
    Process STL file and return results via callback
    
    Request body can be:
    1. JSON with STL URL:
    {
        "stl_url": "https://example.com/model.stl",
        "callback_url": "https://your-api.com/callback",
        "file_id": "optional_file_identifier",
        "max_dimensions": {"x": 300, "y": 300, "z": 300}  // optional
    }
    
    2. Form-data with STL file upload:
    - stl_file: STL file
    - callback_url: callback URL
    - file_id: optional file identifier 
    - max_x, max_y, max_z: optional dimension limits
    """
    try:
        # Check if it's JSON request (URL) or form-data (file upload)
        if request.is_json:
            data = request.get_json()
            stl_url = data.get('stl_url')
            callback_url = data.get('callback_url')
            file_id = data.get('file_id')
            max_dimensions = data.get('max_dimensions', {'x': 300, 'y': 300, 'z': 300})
            
            if not stl_url or not callback_url:
                return jsonify({"error": "stl_url and callback_url are required"}), 400
            
            # Download file from URL
            filename = f"{file_id or 'temp'}_{int(time.time())}.stl"
            file_path = download_file_from_url(stl_url, tmp_directory, filename)
            
            if not file_path:
                error_data = {
                    "file_id": file_id,
                    "status": "error",
                    "error": "Failed to download STL file from URL",
                    "timestamp": time.time()
                }
                send_callback(callback_url, error_data)
                return jsonify({"error": "Failed to download STL file"}), 400
                
        else:
            # Handle file upload
            if 'stl_file' not in request.files:
                return jsonify({"error": "No STL file provided"}), 400
            
            file = request.files['stl_file']
            callback_url = request.form.get('callback_url')
            file_id = request.form.get('file_id')
            
            if not callback_url:
                return jsonify({"error": "callback_url is required"}), 400
            
            if file.filename == '':
                return jsonify({"error": "No file selected"}), 400
            
            if not file.filename.lower().endswith('.stl'):
                return jsonify({"error": "File must be an STL file"}), 400
            
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
                process_stl_file(file_path, callback_url, file_id, max_dimensions)
                gc.collect()
        
        thread = threading.Thread(target=process_async)
        thread.start()
        
        return jsonify({
            "message": "STL processing started", 
            "file_id": file_id,
            "status": "processing"
        }), 202
        
    except Exception as e:
        logging.error(f"Error in slice_stl endpoint: {str(e)}")
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "version": version,
        "timestamp": time.time()
    }), 200


# run app so it can be run with flask
if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5030, debug=True)

