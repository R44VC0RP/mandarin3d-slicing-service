from flask import Flask, request, jsonify
from filemanagement import get_all_files, download_file, put_file, upload_single_file
import threading
import os
from dotenv import load_dotenv
import printslicer as ps
import imagerender as ir
import connector as cn
import logging
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
    spool_price = cn.get_price_per_spool()
    price_per_gram = float(spool_price) / 1000
    good_price = round(mass * price_per_gram * 1.1, 2)
    better_price = round(mass * price_per_gram * 1.2, 2)
    best_price = round(mass * price_per_gram * 1.4, 2)

    return {
        "good_price": good_price,
        "better_price": better_price,
        "best_price": best_price
    }

    

def process_files(prefix):
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
            response = ps.get_mass(location)
            logging.info(f"Mass response: {response}")
            
            # Check if the mass calculation was successful
            if response['status'] == 200:
                logging.info(f"Rendering STL to PNG")
                # Convert the STL file to a PNG image
                png_path = ir.render_stl_to_png(location)
                
                # If the PNG was successfully created, upload it to S3
                if png_path != None:
                    logging.info(f"Uploading PNG to S3")
                    upload_single_file(png_path, prefix)
                    # Remove the PNG file after uploading
                    os.remove(png_path)
                
                # After processing, delete the original STL file
                logging.info(f"Deleting STL file {location}")
                os.remove(location)
                logging.info(f"Deleted STL file {location}")

                # Calculate pricing tiers based on the mass of the STL file
                mass = response['mass']
                pricing = caclulate_pricing_tiers(mass)
                # Update the order with the calculated mass and pricing information
                cn.update_order(prefix, file, mass, pricing, png_path)
            else:
                # If the mass calculation failed, update the order status accordingly
                cn.update_order_failed_slice(prefix, file, response['message'])
                logging.error(f"Failed to slice file {file}. Reason: {response['message']}")
    logging.info(f"Finished processing files for {prefix}")


            

@app.route('/api/slice/<prefix>', methods=['POST'])
def handle_request(prefix):    
    try:
        thread = threading.Thread(target=process_files, args=(prefix,))
        thread.start()
        print(f"Process started for {prefix}")
        return jsonify({"message": f"Process started for {prefix}"}), 202
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# run app so it can be run with flask
if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5030)

