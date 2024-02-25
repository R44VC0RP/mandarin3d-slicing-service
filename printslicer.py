import subprocess
import re
import os
import logging
import logging

# Set up the logger
#setup_logging()

# Get the logger


def get_mass(filename):
    response = {}
    try:
        relative_slic3r_dir = 'Slic3r'
        slic3r_dir = os.path.join(os.getcwd(), relative_slic3r_dir)
        slic3r_exec = os.path.join(slic3r_dir, 'Slic3r')
        base_name, _ = os.path.splitext(os.path.basename(filename))
        gcode_file = os.path.join(os.path.dirname(filename), f'{base_name}.gcode')

        # Slice the STL file to G-code
        slice_command = f'{slic3r_exec} --load config.ini "{filename}" --support-material -o "{gcode_file}"'
        
        # Using subprocess.run instead of subprocess.Popen
        result = subprocess.run(slice_command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=slic3r_dir, text=True)
        
        stdout = result.stdout
        stderr = result.stderr
        logging.info(f'Stdout: {stdout}')
        logging.info(f'Stderr: {stderr}')
        
        volume_match = re.search(r'Filament required: \d+\.\d+mm \((\d+\.\d+)cm3\)', stdout)
        
        if volume_match:
            volume_cm3 = float(volume_match.group(1))  # Volume in cubic centimeters
            density = 1.25  # Density of the material in g/cm³ (assuming PLA)
            mass = volume_cm3 * density  # Mass in grams
            logging.info(f"Filename: {filename} and Mass: {mass} g")
            response['status'] = 200
            response['mass'] = mass
        else:
            logging.error(f'Volume information not found for {filename}')
            response['status'] = 400
            response['error'] = 'Volume information not found'

        # Delete the G-code file
        if os.path.exists(gcode_file):
            os.remove(gcode_file)
            logging.info(f'Deleted {gcode_file}')
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
