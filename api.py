from flask import Flask, request, jsonify
from filemanagement import get_all_files, download_file, put_file, upload_single_file
import threading
import os
from dotenv import load_dotenv
import printslicer as ps
import imagerender as ir
import connector as cn

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
    files = get_all_files(prefix)
    for file in files:
        if file.lower().endswith('.stl'):
            print(f"Processing file {file}")
            location = download_file(file, prefix, tmp_directory)
            # change from relative to absolute path
            location = os.path.abspath(location)
            response = ps.get_mass(location)
            png_path = ir.render_stl_to_png(location)
            upload_single_file(png_path, prefix)

            # delete the files
            os.remove(location)
            os.remove(png_path)

            if response['status'] == 200:
                mass = response['mass']
                pricing = caclulate_pricing_tiers(mass)
                cn.update_order(prefix, file, mass, pricing)
            else:
                cn.update_order_failed_slice(prefix, file, response['message'])

@app.route('/api/slice/<prefix>', methods=['POST'])
def handle_request(prefix):    
    try:
        thread = threading.Thread(target=process_files, args=(prefix,))
        thread.start()
        return jsonify({"message": "Process started"}), 202
    except Exception as e:
        return jsonify({"error": str(e)}), 500

#process_files('or_4fbvlz40cvt')

# run app so it can be run with flask
if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5030)

