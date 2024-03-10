from flask import Flask, request, jsonify
from filemanagement import get_all_files, download_file, put_file, upload_single_file
import threading
import os
from dotenv import load_dotenv
import printslicer as ps
import imagerender as ir
import connector as cn
import logging
import gc
import time
import requests
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', filename='slicer.log', filemode='w')



dotenv_path = '.env'  # or specify the full path to the file

# Load the environment variables from your .env file
load_dotenv(dotenv_path=dotenv_path)



app = Flask(__name__)

tmp_directory = 'tmp'
# check if the tmp directory exists
if not os.path.exists(tmp_directory):
    os.makedirs(tmp_directory)

def caclulate_pricing_tiers(mass):
    mass = float(mass)
    spool_price = cn.get_price_per_spool()
    logging.info(f"Spool price: {spool_price}")
    price_per_gram = float(spool_price) / 1000
    good_price = round(mass * price_per_gram * 1.1, 2)
    better_price = round(mass * price_per_gram * 1.2, 2)
    best_price = round(mass * price_per_gram * 1.4, 2)

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
                return "Failed to send request to production"
    except Exception as e:
        return f"Failed to send request to development. Reason: {str(e)}"
    

def process_files(prefix):
    entire_file_time_start = time.time()
    # Retrieve all files with the given prefix
    files = get_all_files(prefix)
    print(f"Files found: {files}")
    logging.info(f"Files found: {files}")
    
    # Iterate through each file found
    for file in files:
        # Check if the file is an STL file based on its extension
        if file.lower().endswith('.stl'):
            print(f"Processing file {file}")
            logging.info(f"Processing file {file}")
            
            # Download the STL file to a temporary directory and get its location
            location = download_file(file, prefix, tmp_directory)
            # Convert the file location from a relative path to an absolute path
            location = os.path.abspath(location)
            
            # Get the mass of the STL file by processing it
            slicing_start_time = time.time()
            response = ps.get_mass(location)
            slicing_end_time = time.time()
            logging.info(f"Mass response: {response}")
            
            # Check if the mass calculation was successful
            if response['status'] == 200:
                logging.info(f"Rendering STL to PNG")
                # Convert the STL file to a PNG image
                image_start_time = time.time()

                png_path = ir.render_stl_to_png(location)
                image_end_time = time.time()
                logging.info(f"Rendering STL to PNG took {image_end_time - image_start_time} seconds")
                
                # If the PNG was successfully created, upload it to S3
                if png_path != None:
                    logging.info(f"Uploading PNG to S3")
                    upload_single_file(png_path, prefix)
                    # Remove the PNG file after uploading
                    os.remove(png_path)
                    prefix_png = png_path.split("/")[-1]
                    png_url = f"https://s2.mandarin3d.com/{prefix}/{prefix_png}"
                    
                
                # After processing, delete the original STL file
                logging.info(f"Deleting STL file {location}")
                os.remove(location)
                logging.info(f"Deleted STL file {location}")

                # Calculate pricing tiers based on the mass of the STL file
                mass = response['mass']
                pricing = caclulate_pricing_tiers(mass)
                # Update the order with the calculated mass and pricing information
                total_time_end = time.time()
                cn.update_order(prefix, file, mass, pricing, png_url)
                total_processing = total_time_end - entire_file_time_start
                logging.info(f"Total processing time for {file} took {total_processing} seconds")
                mass_processing = slicing_end_time - slicing_start_time
                logging.info(f"Mass processing time for {file} took {mass_processing} seconds")
                image_processing = image_end_time - image_start_time
                logging.info(f"Image processing time for {file} took {image_processing} seconds")
                stats = {
                    "total_processing": total_processing,
                    "mass_processing": mass_processing,
                    "image_processing": image_processing
                }
                cn.upload_stats(prefix, file, stats)
                print(f"Finished processing file {file}")
                print(f"Total processing time for {file} took {total_processing} seconds")
                print(f"Mass processing time for {file} took {mass_processing} seconds")
                print(f"Image processing time for {file} took {image_processing} seconds")

                
            else:
                # If the mass calculation failed, update the order status accordingly
                cn.update_order_failed_slice(prefix, file, response['message'])
                logging.error(f"Failed to slice file {file}. Reason: {response['message']}")
    logging.info(f"Finished processing files for {prefix}")
    print(f"Finished processing files for {prefix}")
    response = api_hit_when_all_files_sliced(prefix)
    print(response)
    logging.info(response)
    gc.collect()


            

@app.route('/api/slice/<prefix>', methods=['POST'])
def handle_request(prefix):    
    try:
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

    cn.update_order(prefix, filename, mass, pricing, png)

    return jsonify({"message": f"Sliced Order Successfuly for {order_number}"}), 202

# run app so it can be run with flask
if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5030)

