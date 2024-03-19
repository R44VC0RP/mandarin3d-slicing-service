from flask import Flask, request, jsonify
from filemanagement import get_all_files, download_file, put_file, upload_single_file
import threading
import os
from dotenv import load_dotenv
import printslicer as ps
import _old.imagerender as ir
import connector as cn
import logging
import gc
import time
import requests

from logging.config import dictConfig

dictConfig({
    'version': 1,
    'formatters': {'default': {
        'format': '[%(asctime)s] %(levelname)s in %(module)s: %(message)s',
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




dotenv_path = '.env'  # or specify the full path to the file

# Load the environment variables from your .env file
load_dotenv(dotenv_path=dotenv_path)



app = Flask(__name__)

tmp_directory = 'tmp'
# check if the tmp directory exists
if not os.path.exists(tmp_directory):
    os.makedirs(tmp_directory)



def caclulate_pricing_tiers(mass):
    profit_margin = float(cn.get_profit_margin())
    mass = float(mass)
    spool_price = cn.get_price_per_spool()
    price_per_gram = float(spool_price) / 1000
    good_price = round(mass * price_per_gram * 1.1 * profit_margin + 0.20, 2)
    better_price = round(mass * price_per_gram * 1.2 * profit_margin + 0.20, 2)
    best_price = round(mass * price_per_gram * 1.4 * profit_margin + 0.20, 2)

    return {
        "good_price": good_price,
        "better_price": better_price,
        "best_price": best_price
    }

def api_hit_when_all_files_sliced(prefix):
    # This function will be called when all files are sliced, also I do not want to actively update if we are working on development or production. So first send request to developement, and if that fails, send request to production
    # development api url: https://dev.mandarin3d.com/api/slice/complete/<prefix>
    # production api url: https://mandarin3d.com/api/slice/complete/<prefix>
    try:
        response = requests.post(f"https://dev.mandarin3d.com/api/slice/complete/{prefix}")
        
        if response.status_code == 200:
            return "Request sent to development"
        else:
            response = requests.post(f"https://mandarin3d.com/api/slice/complete/{prefix}")
            if response.status_code == 200:
                return "Request sent to production"
            else:
                return "Failed to send request to production and development. Reason: Unknown"
    except Exception as e:
        return f"Failed to send request to development. Reason: {str(e)}" 

def api_hit_when_all_files_sliced_2(prefix, cart_id):
    # This function will be called when all files are sliced, also I do not want to actively update if we are working on development or production. So first send request to developement, and if that fails, send request to production
    # development api url: https://dev.mandarin3d.com/api/slice/complete/<prefix>
    # production api url: https://mandarin3d.com/api/slice/complete/<prefix>
    try:
        response = requests.post(f"https://dev.mandarin3d.com/api/2/slice/complete/{prefix}/{cart_id}")
        
        if response.status_code == 200:
            return "Request sent to development"
        else:
            response = requests.post(f"https://mandarin3d.com/api/2/slice/complete/{prefix}/{cart_id}")
            if response.status_code == 200:
                return "Request sent to production"
            else:
                return "Failed to send request to production and development. Reason: Unknown"
    except Exception as e:
        return f"Failed to send request to development. Reason: {str(e)}"

def process_file(file, prefix):
    logging.info("STARTING FILE - " + file)
    entire_file_time_start = time.time()
    print(f"Processing file {file}")
    logging.info(f"Processing file {file}")
    
    # Check if the file is an STL file based on its extension
    if file.lower().endswith('.stl'):
        # Download the STL file to a temporary directory and get its location
        location = download_file(file, prefix, tmp_directory)
        # Convert the file location from a relative path to an absolute path
        location = os.path.abspath(location)
        
        # Get the mass of the STL file by processing it
        slicing_start_time = time.time()
        start_time_get_mass = time.time()
        # response = ps.get_mass(location)
        # Phasing out the old memory intensive method for the less memory intensive method. 
        # end_time_get_mass = time.time()
        # logging.info(f"TIME Time taken for get_mass: {end_time_get_mass - start_time_get_mass} seconds")

        start_time_run_slicer = time.time()
        response = ps.run_slicer_command_and_extract_info(location, file)
        end_time_run_slicer = time.time()
        logging.info(f"TIME Time taken for run_slicer_command_and_extract_info: {end_time_run_slicer - start_time_run_slicer} seconds") 
        slicing_end_time = time.time()
        logging.info(f"FIND Mass response: {response}")
        
        # Check if the mass calculation was successful
        if response['status'] == 200:
            os.remove(location)
            if response['size_x'] > 225 or response['size_y'] > 225 or response['size_z'] > 225:
                
                if response['size_x'] > 225:
                    dimension = 'X'
                elif response['size_y'] > 225:
                    dimension = 'Y'
                else:
                    dimension = 'Z'
                cn.update_order_failed_slice(prefix, file, f"Dimension {dimension} too large, Model is {float(response['size_x']):.2f}x{float(response['size_y']):.2f}x{float(response['size_z']):.2f}.")
                logging.error(f"Failed to slice file {file}. Reason: Dimension {dimension} too large.")
            else:
                # Calculate pricing tiers based on the mass of the STL file
                mass = response['mass']
                pricing = caclulate_pricing_tiers(mass)
                # Update the order with the calculated mass and pricing information
                total_time_end = time.time()
                cn.update_order(prefix, file, mass, pricing)
                total_processing = total_time_end - entire_file_time_start
                # logging.info(f"Total processing time for {file} took {total_processing} seconds")
                mass_processing = slicing_end_time - slicing_start_time
                # logging.info(f"Mass processing time for {file} took {mass_processing} seconds")
                stats = {
                    "total_processing": total_processing,
                    "mass_processing": mass_processing
                }
                cn.upload_stats(prefix, file, stats)
                # print(f"Finished processing file {file}")
                # print(f"Total processing time for {file} took {total_processing} seconds")
                # print(f"Mass processing time for {file} took {mass_processing} seconds")                
        else:
            # If the mass calculation failed, update the order status accordingly
            cn.update_order_failed_slice(prefix, file, response['error'])
            logging.error(f"Failed to slice file {file}. Reason: {response['error']}")


def process_file_v2(file, prefix, cart_id):
    logging.info("STARTING FILE - " + file)
    entire_file_time_start = time.time()
    print(f"Processing file {file}")
    logging.info(f"Processing file {file}")
    
    # Check if the file is an STL file based on its extension
    if file.lower().endswith('.stl'):
        # Download the STL file to a temporary directory and get its location
        location = download_file(file, prefix, tmp_directory)
        # Convert the file location from a relative path to an absolute path
        location = os.path.abspath(location)
        
        # Get the mass of the STL file by processing it
        slicing_start_time = time.time()

        # response = ps.get_mass(location)
        # Phasing out the old memory intensive method for the less memory intensive method. 
        # end_time_get_mass = time.time()
        # logging.info(f"TIME Time taken for get_mass: {end_time_get_mass - start_time_get_mass} seconds")

        start_time_run_slicer = time.time()
        response = ps.run_slicer_command_and_extract_info(location, file)
        end_time_run_slicer = time.time()
        logging.info(f"TIME Time taken for run_slicer_command_and_extract_info: {end_time_run_slicer - start_time_run_slicer} seconds") 
        slicing_end_time = time.time()
        logging.info(f"FIND Mass response: {response}")
        
        # Check if the mass calculation was successful
        if response['status'] == 200:
            os.remove(location)
            if response['size_x'] > 225 or response['size_y'] > 225 or response['size_z'] > 225:
                
                if response['size_x'] > 225:
                    dimension = 'X'
                elif response['size_y'] > 225:
                    dimension = 'Y'
                else:
                    dimension = 'Z'
                cn.update_file_failed(file, f"Dimension {dimension} too large, Model is {float(response['size_x']):.2f}x{float(response['size_y']):.2f}x{float(response['size_z']):.2f}.")
                logging.error(f"Failed to slice file {file}. Reason: Dimension {dimension} too large.")
            else:
                # Calculate pricing tiers based on the mass of the STL file
                mass = response['mass']
                pricing = caclulate_pricing_tiers(mass)
                # Update the order with the calculated mass and pricing information
                total_time_end = time.time()
                cn.update_file(file, mass, pricing)
                total_processing = total_time_end - entire_file_time_start
                # logging.info(f"Total processing time for {file} took {total_processing} seconds")
                mass_processing = slicing_end_time - slicing_start_time
                # logging.info(f"Mass processing time for {file} took {mass_processing} seconds")
                stats = {
                    "total_processing": total_processing,
                    "mass_processing": mass_processing
                }
                cn.upload_stats(prefix, file, stats)
        else:
            # If the mass calculation failed, update the order status accordingly
            cn.update_file_failed(file, response['error'])
            logging.error(f"Failed to slice file {file}. Reason: {response['error']}")

def process_files(prefix):
    with app.app_context():  # Push an application context
        # Retrieve all files with the given prefix
        files = get_all_files(prefix)
        print(f"Files found: {files}")
        logging.info(f"Files found: {files}")
        
        threads = []
        # Create a thread for each file found and start them
        for file in files:
            thread = threading.Thread(target=process_file, args=(file, prefix))
            threads.append(thread)
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        logging.info(f"Finished processing files for {prefix}")
        print(f"Finished processing files for {prefix}")
        response = api_hit_when_all_files_sliced(prefix)
        print(response)
        logging.info(response)
        gc.collect()
        return jsonify({"message": "Sliced Order Successfully"}), 202
    

def process_files_2(prefix, cart_id):
    with app.app_context():  # Push an application context
        # Retrieve all files with the given prefix
        files = get_all_files(prefix)
        print(f"Files found: {files}")
        logging.info(f"Files found: {files}")
        
        threads = []
        # Create a thread for each file found and start them
        for file in files:
            thread = threading.Thread(target=process_file_v2, args=(file, prefix, cart_id))
            threads.append(thread)
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        logging.info(f"Finished processing files for {prefix}")
        print(f"Finished processing files for {prefix}")
        response = api_hit_when_all_files_sliced_2(prefix, cart_id)
        print(response)
        logging.info(response)
        gc.collect()
        return jsonify({"message": "Sliced Order Successfully"}), 202

@app.route('/api/slice/<prefix>', methods=['POST'])
def handle_request(prefix):    
    try:
        # Start the processing in a separate thread to not block the main thread
        thread = threading.Thread(target=process_files, args=(prefix,))
        thread.start()
        print(f"Process started for {prefix}")
        return jsonify({"message": f"Process started for {prefix}"}), 202
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/slice/manual/<prefix>', methods=['POST'])
def handle_manual_request(prefix):
    data = request.get_json()
    name = data['name'] 
    mass = data['mass']
    order_number = data['order_number']

    pricing = caclulate_pricing_tiers(mass)

    png = "https://s2.mandarin3d.com/manual-m.png"

    filename = prefix + "/" + name

    cn.update_order(prefix, filename, mass, pricing)

    return jsonify({"message": f"Sliced Order Successfully for {order_number}"}), 202

@app.route('/2/api/slice/<prefix>/<cart_id>', methods=['POST'])
def handle_request(prefix, cart_id):    
    try:
        # Start the processing in a separate thread to not block the main thread
        thread = threading.Thread(target=process_file_v2, args=(prefix, cart_id,))
        thread.start()
        print(f"Process started for {prefix}")
        return jsonify({"message": f"Process started for {prefix}"}), 202
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# run app so it can be run with flask
if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5030)

