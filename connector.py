from pymongo import MongoClient
from pymongo.server_api import ServerApi
import os
import logging

# Get MongoDB connection string from environment variable
MONGO_DB_CONNECTION_STRING = "mongodb+srv://mandarin3d_access:I9DroD4YdgMpwF5I@cluster0.gkeabiy.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"

# Connect to MongoDB
client = MongoClient(MONGO_DB_CONNECTION_STRING, server_api=ServerApi('1'))

db = client.mandarin3d

def get_order_files(prefix):
    """Get an order from MongoDB."""
    order = db.orders.find_one({"order_id": prefix})
    files = order.get('files', [])
    file_list = []
    for file in files:
        file_list.append(file['filename'])
        
    return file_list

def get_price_per_spool():
    """Get the price per spool from MongoDB."""
    return db.config.find_one({"config": "config"})['spool_price']

def update_order_failed_slice(prefix, filename, message):
    """Update an order in MongoDB."""
    db.orders.update_one({"order_id": prefix}, {"$set": {"status": "failed", "message": message}})
    print(f"Order {prefix} failed to slice. Reason: {message}")
    return "Order updated successfully."

def update_order(prefix, filename, mass, pricing, png_path):
    """Update an order in MongoDB."""
    document_found = db.orders.find_one({"order_id": prefix})
    fileid_active = None
    logging.info(document_found['files'])
    for fileid, fileinfo in document_found['files'].items():
        if fileinfo['url'] == filename:
            fileid_active = fileid
            break
    if fileid_active:
        document_found['files'][fileid_active]['pricing'] = pricing
        document_found['files'][fileid_active]['mass'] = mass
        document_found['files'][fileid_active]['status'] = "good"
        document_found['files'][fileid_active]['image'] = png_path
        db.orders.update_one({"order_id": prefix}, {"$set": {"files": document_found['files']}})
    else:
        print(f"No matching file found for {filename} in order {prefix}.")

def update_order_manual_slice(prefix, filename, mass, pricing, png_path):
    docuemntFound = db.orders.find_one({"order_id": prefix})
    for fileid, fileinfo in documentFound['files'].items():
        if fileinfo['url'] == filename:
            fileid_active = fileid
            break
    if fileid_active:
        documentFound['files'][fileid_active]['pricing'] = pricing
        documentFound['files'][fileid_active]['mass'] = mass
        documentFound['files'][fileid_active]['status'] = "good"
        documentFound['files'][fileid_active]['image'] = png_path
        db.orders.update_one({"order_id": prefix}, {"$set": {"files": documentFound['files']}})
    else:
        logging.error(f"No matching file found for {filename} in order {prefix}.")
    logging.error(f"Order {prefix} failed to slice. Reason: {message}")

def update_order_failed_slice(prefix, filename, message):
    """Update an order in MongoDB."""

    documentFound = db.orders.find_one({"order_id": prefix})
    fileid_active = None
    for fileid, fileinfo in documentFound['files'].items():
        if fileinfo['url'] == filename:
            fileid_active = fileid
            break
    if fileid_active:
        documentFound['files'][fileid_active]['status'] = "failed"
        documentFound['files'][fileid_active]['message'] = message
        db.orders.update_one({"order_id": prefix}, {"$set": {"files": documentFound['files']}})
    else:
        print(f"No matching file found for {filename} in order {prefix}.")
    print(f"Order {prefix} failed to slice. Reason: {message}")
    return "Order updated successfully."

def upload_stats(prefix, file, stats):
    """Upload slicing stats to MongoDB."""
    db.slicing_stats.insert_one({"order_id": prefix, "stats": stats, "file": file})
    return "Stats uploaded successfully."

