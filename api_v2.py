from flask import Blueprint, request, jsonify
import time
import os
import logging
import printslicer as ps
from pymongo import MongoClient
from pymongo.server_api import ServerApi
import os
import logging
import requests

api_v2_blueprint = Blueprint('api_v2', __name__)
DEV_MONGO_DB_CONNECTION_STRING = "mongodb+srv://m3d-express:DdC3ShCPB5SRW3Hc@cluster0.gkeabiy.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
PROD_MONGO_DB_CONNECTION_STRING = "mongodb+srv://m3d-express:DdC3ShCPB5SRW3Hc@cluster0.gkeabiy.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"

def download_file(file_url, download_path='tmp'):
    try:
        # Ensure the download path exists
        os.makedirs(download_path, exist_ok=True)
        
        # Extract the file name from the URL
        file_name = os.path.basename(file_url)
        download_path_full = os.path.join(download_path, file_name)
        
        # Download the file
        response = requests.get(file_url, stream=True)
        if response.status_code == 200:
            with open(download_path_full, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            return download_path
        else:
            logging.error(f"Failed to download file from {file_url}. Status code: {response.status_code}")
            return None
    except Exception as e:
        logging.error(f"An error occurred while downloading the file: {e}")
        return None

def get_file_from_db(fileid, env):
    if env == "dev":
        client = MongoClient(DEV_MONGO_DB_CONNECTION_STRING, server_api=ServerApi('1'))
        db = client.m3d_express_dev
    else:
        client = MongoClient(PROD_MONGO_DB_CONNECTION_STRING, server_api=ServerApi('1'))
        db = client.m3d_express_prod
    
    file_object = db.files.find_one({"fileid": fileid})
    return file_object

def get_configs_from_db(env):
    if env == "dev":
        client = MongoClient(DEV_MONGO_DB_CONNECTION_STRING, server_api=ServerApi('1'))
        db = client.m3d_express_dev
    else:
        client = MongoClient(PROD_MONGO_DB_CONNECTION_STRING, server_api=ServerApi('1'))
        db = client.m3d_express_prod
    configs = db.configs.find_one({})
    return configs

def update_file_status(fileid, env, status, error=None, mass=None, dimensions=None):
    if env == "dev":
        client = MongoClient(DEV_MONGO_DB_CONNECTION_STRING, server_api=ServerApi('1'))
        db = client.m3d_express_dev
    else:
        client = MongoClient(PROD_MONGO_DB_CONNECTION_STRING, server_api=ServerApi('1'))
        db = client.m3d_express_prod
    if error is None:
        db.files.update_one({"fileid": fileid}, {"$set": {"file_status": status, "mass_in_grams": mass, "dimensions": dimensions}})
    else:
        db.files.update_one({"fileid": fileid}, {"$set": {"file_status": status, "file_error": error}})

def process_file_v3(file_object):
    logging.info("STARTING FILE - " + file_object['filename'] + " - " + file_object['fileid'])
    entire_file_time_start = time.time()
    logging.info(f"Processing file {file_object['filename']}")
    
    # Check if the file is an STL file based on its extension
    if file_object['filename'].lower().endswith('.stl'):
        # Download the STL file to a temporary directory and get its location
        location = download_file(file_object['url'])
        # Convert the file location from a relative path to an absolute path
        location = os.path.abspath(location)
        
        # Get the mass of the STL file by processing it
        slicing_start_time = time.time()

        # response = ps.get_mass(location)
        # Phasing out the old memory intensive method for the less memory intensive method. 
        # end_time_get_mass = time.time()
        # logging.info(f"TIME Time taken for get_mass: {end_time_get_mass - start_time_get_mass} seconds")

        start_time_run_slicer = time.time()
        response = ps.run_slicer_command_and_extract_info(location, file_object['filename'])
        end_time_run_slicer = time.time()
        logging.info(f"TIME Time taken for run_slicer_command_and_extract_info: {end_time_run_slicer - start_time_run_slicer} seconds") 
        slicing_end_time = time.time()
        logging.info(f"FIND Mass response: {response}")
        
        # Check if the mass calculation was successful
        if response['status'] == 200:
            os.remove(location)
            configs = get_configs_from_db(file_object['env'])
            if response['size_x'] > configs['dimensionConfig']['x'] or response['size_y'] > configs['dimensionConfig']['y'] or response['size_z'] > configs['dimensionConfig']['z']:
                if response['size_x'] > configs['dimensionConfig']['x']:
                    dimension = 'X'
                    logging.error(f"Failed to slice file {file_object['filename']}. Reason: Dimension {dimension} too large.")
                    update_file_status(file_object['fileid'], file_object['env'], "error", f"Dimension {dimension} too large. {dimension} is {response['size_x']}mm.")
                elif response['size_y'] > configs['dimensionConfig']['y']:
                    dimension = 'Y'
                    logging.error(f"Failed to slice file {file_object['filename']}. Reason: Dimension {dimension} too large.")
                    update_file_status(file_object['fileid'], file_object['env'], "error", f"Dimension {dimension} too large. {dimension} is {response['size_y']}mm.")
                elif response['size_z'] > configs['dimensionConfig']['z']:
                    dimension = 'Z'
                    logging.error(f"Failed to slice file {file_object['filename']}. Reason: Dimension {dimension} too large.")
                    update_file_status(file_object['fileid'], file_object['env'], "error", f"Dimension {dimension} too large. {dimension} is {response['size_z']}mm.")
            else:
                # Calculate pricing tiers based on the mass of the STL file
                mass = response['mass']
                # Update the order with the calculated mass and pricing information
                total_time_end = time.time()
                total_processing = total_time_end - entire_file_time_start
                # logging.info(f"Total processing time for {file} took {total_processing} seconds")
                mass_processing = slicing_end_time - slicing_start_time
                # logging.info(f"Mass processing time for {file} took {mass_processing} seconds")
                stats = {
                    "total_processing": total_processing,
                    "mass_processing": mass_processing
                }
                dims = {
                    "x": response['size_x'],
                    "y": response['size_y'],
                    "z": response['size_z']
                }
                logging.info(f"Stats: {stats}")
                update_file_status(file_object['fileid'], file_object['env'], "success", dimensions=dims)
        else:
            # If the mass calculation failed, update the order status accordingly
            logging.error(f"Failed to slice file {file_object['filename']}. Reason: {response['error']}")
            update_file_status(file_object['fileid'], file_object['env'], "error", f"Failed to slice file. Reason: {response['error']}")


@api_v2_blueprint.route('/api/slice', methods=['POST'])
def handle_request_v2():
    # Get the file object from the database
    fileid = request.json['fileid']
    env = request.json['env']
    # Get the file object from the database
    file_object = get_file_from_db(fileid, env)
    process_file_v3(file_object)
    # Your v2 logic here
    pass

