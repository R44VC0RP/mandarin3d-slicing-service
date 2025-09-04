import subprocess
import re
import os
import logging
import random
import time
from stl import mesh
import numpy as np

# Configure logging for printslicer module if not already configured
if not logging.getLogger().handlers:
    logging.basicConfig(
        level=logging.INFO,
        format='[%(asctime)s] %(levelname)s in %(module)s:%(funcName)s:%(lineno)d: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

def scale_stl(filename, scale_factor, output_filename):
    """Scale STL file by given factor"""
    logging.info(f"[SCALE_STL] Starting STL scaling: {filename} -> {output_filename}")
    logging.info(f"[SCALE_STL] Scale factor: {scale_factor}")
    
    try:
        # Check input file exists
        if not os.path.exists(filename):
            raise FileNotFoundError(f"Input STL file not found: {filename}")
            
        input_size = os.path.getsize(filename)
        logging.info(f"[SCALE_STL] Input file size: {input_size} bytes")
        
        # Load the STL file
        logging.info(f"[SCALE_STL] Loading STL mesh from: {filename}")
        your_mesh = mesh.Mesh.from_file(filename)
        logging.info(f"[SCALE_STL] Loaded mesh with {len(your_mesh.vectors)} faces")
        
        # Scale the mesh
        logging.info(f"[SCALE_STL] Applying scale factor: {scale_factor}")
        your_mesh.vectors *= scale_factor
        
        # Save the scaled mesh
        logging.info(f"[SCALE_STL] Saving scaled mesh to: {output_filename}")
        your_mesh.save(output_filename)
        
        # Verify output
        if os.path.exists(output_filename):
            output_size = os.path.getsize(output_filename)
            logging.info(f"[SCALE_STL] Successfully saved scaled STL, size: {output_size} bytes")
        else:
            raise Exception("Scaled STL file was not created")
            
    except Exception as e:
        logging.error(f"[SCALE_STL] Failed to scale STL: {str(e)}")
        logging.error(f"[SCALE_STL] Exception type: {type(e).__name__}")
        raise

# Printslicer module initialization
logging.info(f"[PRINTSLICER_INIT] Printslicer module loaded")
logging.info(f"[PRINTSLICER_INIT] Working directory: {os.getcwd()}")
logging.info(f"[PRINTSLICER_INIT] Available functions: scale_stl, get_mass, run_slicer_command_and_extract_info")


def get_mass(filename):
    """Get mass of STL file using Slic3r (legacy function)"""
    logging.info(f"[GET_MASS] ===== STARTING MASS CALCULATION =====")
    logging.info(f"[GET_MASS] Input file: {filename}")
    
    start_time = time.time()
    instance_hash = f"mass_{random.randint(100000, 999999)}"
    logging.info(f"[GET_MASS] Generated instance hash: {instance_hash}")
    
    response = {}
    
    try:
        # Check if input file exists
        if not os.path.exists(filename):
            logging.error(f"[GET_MASS] Input file does not exist: {filename}")
            return {'status': 400, 'error': 'Input file not found'}
        
        file_size = os.path.getsize(filename)
        logging.info(f"[GET_MASS] Input file size: {file_size} bytes")
        
        # Setup paths
        relative_slic3r_dir = 'Slic3r'
        slic3r_dir = os.path.join(os.getcwd(), relative_slic3r_dir)
        slic3r_exec = os.path.join(slic3r_dir, 'Slic3r')
        
        logging.info(f"[GET_MASS] Slic3r directory: {slic3r_dir}")
        logging.info(f"[GET_MASS] Slic3r executable: {slic3r_exec}")
        
        # Check if Slic3r exists
        if not os.path.exists(slic3r_exec):
            logging.error(f"[GET_MASS] Slic3r executable not found: {slic3r_exec}")
            return {'status': 500, 'error': 'Slic3r executable not found'}
        
        # Generate G-code filename
        base_name, _ = os.path.splitext(os.path.basename(filename))
        gcode_file = os.path.join(os.path.dirname(filename), f'{instance_hash}_{base_name}.gcode')
        logging.info(f"[GET_MASS] Generated G-code filename: {gcode_file}")

        # Build slice command
        slice_command = f'{slic3r_exec} --load config.ini "{filename}" --support-material -o "{gcode_file}"'
        logging.info(f"[GET_MASS] Slice command: {slice_command}")
        
        # Execute slicing
        logging.info(f"[GET_MASS] Starting Slic3r process...")
        slice_start_time = time.time()
        result = subprocess.run(slice_command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=slic3r_dir, text=True)
        slice_time = time.time() - slice_start_time
        
        logging.info(f"[GET_MASS] Slic3r completed in {slice_time:.2f}s")
        logging.info(f"[GET_MASS] Return code: {result.returncode}")
        
        stdout = result.stdout
        stderr = result.stderr
        
        logging.info(f"[GET_MASS] STDOUT length: {len(stdout)} chars")
        logging.info(f"[GET_MASS] STDERR length: {len(stderr)} chars")

        # Save output to files for debugging
        try:
            with open("slicer_output.txt", "w") as f:
                f.write(stdout)
            with open("slicer_error.txt", "w") as f:
                f.write(stderr)
            logging.info(f"[GET_MASS] Output saved to debug files")
        except Exception as e:
            logging.warning(f"[GET_MASS] Failed to save debug files: {str(e)}")
        
        # Log first part of output for debugging
        if stdout:
            logging.info(f"[GET_MASS] STDOUT sample: {stdout[:500]}...")
        if stderr:
            logging.info(f"[GET_MASS] STDERR sample: {stderr[:500]}...")
        
        # Extract volume information
        logging.info(f"[GET_MASS] Searching for volume information in output...")
        volume_pattern = r'Filament required: \d+\.\d+mm \((\d+\.\d+)cm3\)'
        volume_match = re.search(volume_pattern, stdout)
        
        if volume_match:
            volume_cm3 = float(volume_match.group(1))
            density = 1.25  # Density of PLA in g/cm³
            mass = volume_cm3 * density
            
            logging.info(f"[GET_MASS] Volume found: {volume_cm3} cm³")
            logging.info(f"[GET_MASS] Calculated mass: {mass:.2f}g (using PLA density {density} g/cm³)")
            
            response['status'] = 200
            response['mass'] = mass
        else:
            logging.error(f"[GET_MASS] Volume information not found in output")
            logging.error(f"[GET_MASS] Expected pattern: {volume_pattern}")
            response['status'] = 400
            response['error'] = 'Volume information not found in slicer output'

        # Clean up G-code file
        logging.info(f"[GET_MASS] Cleaning up G-code file: {gcode_file}")
        if os.path.exists(gcode_file):
            try:
                os.remove(gcode_file)
                logging.info(f"[GET_MASS] G-code file removed successfully")
            except Exception as e:
                logging.warning(f"[GET_MASS] Failed to remove G-code file: {str(e)}")
        else:
            logging.warning(f"[GET_MASS] G-code file was not created: {gcode_file}")
            if 'error' not in response:
                response['error'] = f'G-code file was not created'
                response['status'] = 400

    except Exception as e:
        processing_time = time.time() - start_time
        logging.error(f"[GET_MASS] ===== MASS CALCULATION FAILED =====")
        logging.error(f"[GET_MASS] Exception after {processing_time:.2f}s: {str(e)}")
        logging.error(f"[GET_MASS] Exception type: {type(e).__name__}")
        response['status'] = 500
        response['error'] = f'Error processing file: {str(e)}'

    total_time = time.time() - start_time
    logging.info(f"[GET_MASS] ===== MASS CALCULATION COMPLETED =====")
    logging.info(f"[GET_MASS] Total time: {total_time:.2f}s")
    logging.info(f"[GET_MASS] Final status: {response.get('status', 'unknown')}")
    
    return response


def run_slicer_command_and_extract_info(directory_to_stl, filename):
    """Run SuperSlicer command and extract slicing information"""
    logging.info(f"[SLICER] ===== STARTING SLICER ANALYSIS =====")
    logging.info(f"[SLICER] Input file: {directory_to_stl}")
    logging.info(f"[SLICER] Original filename: {filename}")
    
    start_time = time.time()
    
    # Log system information
    logging.info(f"[SLICER] Current working directory: {os.getcwd()}")
    logging.info(f"[SLICER] Python executable: {os.sys.executable}")
    
    # Check if SuperSlicer executable exists
    slicer_path = './slicersuper'
    if os.path.exists(slicer_path):
        logging.info(f"[SLICER] SuperSlicer executable found: {slicer_path}")
        # Check if executable
        if os.access(slicer_path, os.X_OK):
            logging.info(f"[SLICER] SuperSlicer is executable")
        else:
            logging.warning(f"[SLICER] SuperSlicer may not be executable")
    else:
        logging.error(f"[SLICER] SuperSlicer executable not found: {slicer_path}")
    
    # Check if config file exists
    config_path = 'config.ini'
    if os.path.exists(config_path):
        config_size = os.path.getsize(config_path)
        logging.info(f"[SLICER] Config file found: {config_path}, size: {config_size} bytes")
    else:
        logging.error(f"[SLICER] Config file not found: {config_path}")
    
    # Check input STL file
    if os.path.exists(directory_to_stl):
        stl_size = os.path.getsize(directory_to_stl)
        logging.info(f"[SLICER] Input STL exists, size: {stl_size} bytes")
    else:
        logging.error(f"[SLICER] Input STL file not found: {directory_to_stl}")
        return {"status": 400, "error": "Input STL file not found"}
    
    # Generate temporary G-code filename
    gcode_temp = os.urandom(24).hex()
    gcode_file = f'{gcode_temp}.gcode'
    logging.info(f"[SLICER] Generated temp G-code filename: {gcode_file}")
    
    # Build command
    command = ['xvfb-run', '-a', './slicersuper', '--load', 'config.ini', '--export-gcode', '-o', gcode_file, directory_to_stl, '--info']
    command_str = ' '.join(command)
    logging.info(f"[SLICER] Command to execute: {command_str}")
    
    try:
        logging.info(f"[SLICER] Starting SuperSlicer subprocess with 240s timeout...")
        result = subprocess.run(command, capture_output=True, text=True, timeout=240)
        
        execution_time = time.time() - start_time
        logging.info(f"[SLICER] SuperSlicer completed in {execution_time:.2f}s")
        logging.info(f"[SLICER] Return code: {result.returncode}")
        
    except subprocess.TimeoutExpired as e:
        execution_time = time.time() - start_time
        logging.error(f"[SLICER] Command timed out after {execution_time:.2f}s")
        logging.error(f"[SLICER] Timeout exception: {str(e)}")
        
        # Try to get partial output if available
        try:
            if hasattr(e, 'stdout') and e.stdout:
                logging.info(f"[SLICER] Partial stdout: {e.stdout[:1000]}...")
            if hasattr(e, 'stderr') and e.stderr:
                logging.info(f"[SLICER] Partial stderr: {e.stderr[:1000]}...")
        except:
            logging.warning(f"[SLICER] Could not retrieve partial output from timeout")
            
        return {
            "status": 400,
            "error": "Slicer command timed out.",
            "execution_time": execution_time
        }

    # Log the raw output for debugging
    logging.info(f"[SLICER] === COMMAND OUTPUT ANALYSIS ===")
    logging.info(f"[SLICER] STDOUT length: {len(result.stdout)} characters")
    logging.info(f"[SLICER] STDERR length: {len(result.stderr)} characters")
    
    if result.stdout:
        logging.info(f"[SLICER] STDOUT content (first 2000 chars): {result.stdout[:2000]}")
    else:
        logging.warning(f"[SLICER] STDOUT is empty")
        
    if result.stderr:
        logging.info(f"[SLICER] STDERR content (first 2000 chars): {result.stderr[:2000]}")
    else:
        logging.info(f"[SLICER] STDERR is empty")
    
    response = {
        "status": 200
    }
    
    # Check for specific error conditions
    if "Objects could not fit on the bed" in result.stderr:
        logging.error(f"[SLICER] {filename} - Objects could not fit on the bed")
        logging.info(f"[SLICER] This usually means the model is too large for the configured bed size")
        response = {
            "status": 400,
            "error": "Objects could not fit on the bed."
        }
        return response
    if "No extrusions were generated for objects." in result.stderr:
        logging.warning(f"[SLICER] {filename} - No extrusions were generated for objects")
        logging.info(f"[SLICER] This usually means the model is too small, likely created in inches")
        logging.info(f"[SLICER] Attempting to scale by factor 25.4 (inches to mm)...")
        
        try:
            # Scale the STL file
            scale_start_time = time.time()
            scale_stl(directory_to_stl, 25.4, directory_to_stl)
            scale_time = time.time() - scale_start_time
            logging.info(f"[SLICER] Scaling completed in {scale_time:.2f}s")
        except Exception as e:
            logging.error(f"[SLICER] Failed to scale STL: {str(e)}")
            return {
                "status": 400,
                "error": f"Failed to scale STL file: {str(e)}"
            }
        
        # Retry slicing with scaled model (without --load config.ini this time)
        retry_command = ['xvfb-run', '-a', './slicersuper', '--export-gcode', '-o', gcode_file, directory_to_stl, '--info']
        retry_command_str = ' '.join(retry_command)
        logging.info(f"[SLICER] Retry command after scaling: {retry_command_str}")
        
        try:
            logging.info(f"[SLICER] Retrying SuperSlicer with scaled model...")
            retry_start_time = time.time()
            result = subprocess.run(retry_command, capture_output=True, text=True, timeout=240)
            retry_time = time.time() - retry_start_time
            
            logging.info(f"[SLICER] Retry completed in {retry_time:.2f}s")
            logging.info(f"[SLICER] Retry return code: {result.returncode}")
            
            if result.stdout:
                logging.info(f"[SLICER] Retry STDOUT (first 1000 chars): {result.stdout[:1000]}")
            if result.stderr:
                logging.info(f"[SLICER] Retry STDERR (first 1000 chars): {result.stderr[:1000]}")
                
        except subprocess.TimeoutExpired:
            retry_time = time.time() - retry_start_time
            logging.error(f"[SLICER] Retry command timed out after {retry_time:.2f}s")
            return {
                "status": 400,
                "error": "Slicer command timed out after scaling.",
                "execution_time": retry_time
            }

    # Clean up temporary G-code file
    logging.info(f"[SLICER] Cleaning up temporary G-code file: {gcode_file}")
    try:
        if os.path.exists(gcode_file):
            os.remove(gcode_file)
            logging.info(f"[SLICER] Temporary G-code file removed successfully")
        else:
            logging.warning(f"[SLICER] G-code file was not created: {gcode_file}")
    except OSError as e:
        logging.error(f"[SLICER] Error removing G-code file {gcode_file}: {e}")

    
    # Extracting information from STDOUT
    logging.info(f"[SLICER] === EXTRACTING SLICING INFORMATION ===")
    logging.info(f"[SLICER] {filename} - Attempting to extract volume and dimensions from output")
    
    # Define regex patterns for extraction
    volume_pattern = r"volume = (\d+\.\d+)"
    size_x_pattern = r"size_x = (\d+\.\d+)"
    size_y_pattern = r"size_y = (\d+\.\d+)"
    size_z_pattern = r"size_z = (\d+\.\d+)"
    
    logging.info(f"[SLICER] Searching for patterns in STDOUT...")
    logging.info(f"[SLICER] Volume pattern: {volume_pattern}")
    logging.info(f"[SLICER] Size patterns: X={size_x_pattern}, Y={size_y_pattern}, Z={size_z_pattern}")
    
    volume_match = re.search(volume_pattern, result.stdout)
    size_x_match = re.search(size_x_pattern, result.stdout)
    size_y_match = re.search(size_y_pattern, result.stdout)
    size_z_match = re.search(size_z_pattern, result.stdout)
    
    logging.info(f"[SLICER] Pattern matching results:")
    logging.info(f"[SLICER] Volume found: {bool(volume_match)}")
    logging.info(f"[SLICER] Size X found: {bool(size_x_match)}")
    logging.info(f"[SLICER] Size Y found: {bool(size_y_match)}")
    logging.info(f"[SLICER] Size Z found: {bool(size_z_match)}")
    
    if volume_match and size_x_match and size_y_match and size_z_match:
        logging.info(f"[SLICER] {filename} - Successfully found all required information")
        
        # Extract values
        volume = float(volume_match.group(1))
        size_x = float(size_x_match.group(1))
        size_y = float(size_y_match.group(1))
        size_z = float(size_z_match.group(1))
        
        slicing_info = {
            "volume": volume,
            "size_x": size_x,
            "size_y": size_y,
            "size_z": size_z
        }
        
        logging.info(f"[SLICER] Extracted values: Volume={volume}mm³, Size={size_x:.2f}×{size_y:.2f}×{size_z:.2f}mm")
        
        # Calculate mass (assuming PLA with density 1.25 g/cm³)
        mass = volume / 1000 * 1.25
        logging.info(f"[SLICER] Calculated mass: {mass:.2f}g (using PLA density 1.25 g/cm³)")
        
        response['mass'] = mass
        response['size_x'] = size_x
        response['size_y'] = size_y
        response['size_z'] = size_z
        
        total_time = time.time() - start_time
        logging.info(f"[SLICER] ===== SLICER ANALYSIS SUCCESSFUL =====")
        logging.info(f"[SLICER] Total processing time: {total_time:.2f}s")
        
        return response
    else:
        total_time = time.time() - start_time
        logging.error(f"[SLICER] ===== SLICER ANALYSIS FAILED =====")
        logging.error(f"[SLICER] {filename} - Failed to extract required information after {total_time:.2f}s")
        logging.error(f"[SLICER] Missing patterns - Volume: {not volume_match}, X: {not size_x_match}, Y: {not size_y_match}, Z: {not size_z_match}")
        
        # Log full output for debugging
        logging.error(f"[SLICER] === FULL STDOUT FOR DEBUGGING ===")
        logging.error(result.stdout if result.stdout else "<EMPTY>")
        logging.error(f"[SLICER] === FULL STDERR FOR DEBUGGING ===")
        logging.error(result.stderr if result.stderr else "<EMPTY>")
        
        response['status'] = 400
        response['error'] = "Failed to extract slicing information - file may not be sized correctly or slicer failed"
        response['execution_time'] = total_time
        
        return response

