import subprocess
import re
import os
import logging
import random
from stl import mesh
import numpy as np

def scale_stl(filename, scale_factor, output_filename):
    # Load the STL file
    your_mesh = mesh.Mesh.from_file(filename)
    
    # Scale the mesh
    your_mesh.vectors *= scale_factor
    
    # Save the scaled mesh
    your_mesh.save(output_filename)
    print(f"Saved scaled STL to {output_filename}")

# Set up the logger
#setup_logging()

# Get the logger


def get_mass(filename):
    instance_hash = f"mass_{random.randint(100000, 999999)}"
    response = {}
    try:
        relative_slic3r_dir = 'Slic3r'
        slic3r_dir = os.path.join(os.getcwd(), relative_slic3r_dir)
        slic3r_exec = os.path.join(slic3r_dir, 'Slic3r')
        base_name, _ = os.path.splitext(os.path.basename(filename))
        gcode_file = os.path.join(os.path.dirname(filename), f'{instance_hash}_{base_name}.gcode')

        # Slice the STL file to G-code
        slice_command = f'{slic3r_exec} --load config.ini "{filename}" --support-material -o "{gcode_file}"'
        
        # Using subprocess.run instead of subprocess.Popen
        result = subprocess.run(slice_command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=slic3r_dir, text=True)
        
        stdout = result.stdout
        stderr = result.stderr

        with open("slicer_output.txt", "w") as f:
            f.write(stdout)
        with open("slicer_error.txt", "w") as f:
            f.write(stderr)
        # logging.info(f'Stdout: {stdout}')
        # logging.info(f'Stderr: {stderr}')
        
        volume_match = re.search(r'Filament required: \d+\.\d+mm \((\d+\.\d+)cm3\)', stdout)
        
        if volume_match:
            volume_cm3 = float(volume_match.group(1))  # Volume in cubic centimeters
            density = 1.25  # Density of the material in g/cm³ (assuming PLA)
            mass = volume_cm3 * density  # Mass in grams
            # logging.info(f"Filename: {filename} and Mass: {mass} g")
            response['status'] = 200
            response['mass'] = mass
        else:
            logging.error(f'Volume information not found for {filename}')
            response['status'] = 400
            response['error'] = 'Volume information not found'

        # Delete the G-code file
        if os.path.exists(gcode_file):
            os.remove(gcode_file)
            # logging.info(f'Deleted {gcode_file}')
        else:
            logging.error(f'{gcode_file} does not exist')
            if 'error' not in response:
                response['error'] = f'{gcode_file} does not exist'
                response['status'] = 400

    except Exception as e:
        logging.error(f'Error processing file {filename}: {str(e)}')
        response['status'] = 500
        response['error'] = f'Error processing file: {str(e)}'

    return response


def run_slicer_command_and_extract_info(directory_to_stl, filename):
    logging.info(f"{filename} - Running slicer command on directory: {directory_to_stl}")

    gcode_temp = os.urandom(24).hex()
    gcode_file = f'{gcode_temp}.gcode'
    
    command = ['./slicersuper', '--load', 'config.ini', '--export-gcode', '-o', gcode_file, directory_to_stl, '--info']
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=240)
    except subprocess.TimeoutExpired:
        logging.error(f"{filename} - Slicer command timed out.")
        response = {
            "status": 400,
            "error": "Slicer command timed out."
        }
        return response

    response = {
        "status": 200
    }
    if "Objects could not fit on the bed." in result.stderr:
        logging.error(f"{filename} - Objects could not fit on the bed.")
        response = {
            "status": 400,
            "error": "Objects could not fit on the bed."
        }
        return response
    if "No extrusions were generated for objects." in result.stderr:
        logging.info(f"{filename} - No extrusions were generated for objects.")
        # This might mean that it was too small and might have been created in inches.
        scale_stl(directory_to_stl, 25.4, directory_to_stl)

        command = ['./slicersuper', '--export-gcode', '-o', gcode_file, directory_to_stl, '--info']
        try:
            result = subprocess.run(command, capture_output=True, text=True, timeout=240)
        except subprocess.TimeoutExpired:
            logging.error(f"{filename} - Slicer command timed out.")
            response = {
                "status": 400,
                "error": "Slicer command timed out."
            }
            return response

    try:
        os.remove(gcode_file)
    except OSError as e:
        logging.error(f"Error removing file {gcode_file}: {e}")

    
    # Extracting information from STDOUT
    logging.info(f"{filename} - Extracting slicing information from command output.")
    volume_pattern = r"volume = (\d+\.\d+)"
    size_x_pattern = r"size_x = (\d+\.\d+)"
    size_y_pattern = r"size_y = (\d+\.\d+)"
    size_z_pattern = r"size_z = (\d+\.\d+)"
    volume_match = re.search(volume_pattern, result.stdout)
    size_x_match = re.search(size_x_pattern, result.stdout)
    size_y_match = re.search(size_y_pattern, result.stdout)
    size_z_match = re.search(size_z_pattern, result.stdout)
    
    if volume_match and size_x_match and size_y_match and size_z_match:
        logging.info(f"{filename} - Successfully extracted slicing information.")
        slicing_info = {
            "volume": float(volume_match.group(1)),
            "size_x": float(size_x_match.group(1)),
            "size_y": float(size_y_match.group(1)),
            "size_z": float(size_z_match.group(1))
        }
        response['mass'] = slicing_info['volume'] / 1000 * 1.25  # Assuming PLA with density 1.25 g/cm³
        response['size_x'] = slicing_info['size_x']
        response['size_y'] = slicing_info['size_y']
        response['size_z'] = slicing_info['size_z']
        return response
    else:
        logging.error(f"{filename} - Failed to extract slicing information from command output.\nHere is more information:")
        logging.error(result.stdout)
        logging.error(result.stderr)
        response['status'] = 400
        response['error'] = "This file is not sized correctly."
        return response

