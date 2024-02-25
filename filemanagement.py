from werkzeug.utils import secure_filename
import boto3
import os
from dotenv import load_dotenv
from werkzeug.datastructures import FileStorage  # Import if not already imported




# Cloudflare R2 credentials and endpoint from .env
ACCESS_KEY = os.getenv('CLD_FLARE_R2_ACCESS')
SECRET_KEY = os.getenv('CLD_FLARE_R2_SECRET')
SESSION_TOKEN = os.getenv('CLD_FLARE_R2_TOKEN')  # Not always needed
R2_ENDPOINT = os.getenv('CLD_FLARE_R2_S3_ENDPOINT')



from botocore.exceptions import NoCredentialsError

# Initialize a session using Cloudflare R2 credentials
session = boto3.session.Session()
client = session.client('s3',
                        region_name='auto',  # Specify the appropriate region
                        endpoint_url=R2_ENDPOINT,  # Your Cloudflare R2 endpoint from .env
                        aws_access_key_id=ACCESS_KEY,  # Access key from .env
                        aws_secret_access_key=SECRET_KEY)  # Secret key from .env

bucket_name = 'mandarin3d'  # Your Cloudflare R2 bucket name


def upload_single_file(file_or_path, prefix, filename=None):
    """Upload a single file to Cloudflare R2 storage. Now supports file path."""
    try:
        # Determine if the input is a file path or a file object
        if isinstance(file_or_path, str):  # If it's a file path
            file_path = file_or_path
            # Use the provided filename or extract from the file path
            secure_name = secure_filename(filename if filename else os.path.basename(file_path))
            with open(file_path, 'rb') as file:
                client.upload_fileobj(file, bucket_name, f'{prefix}/{secure_name}')
        else:  # It's a file object
            secure_name = secure_filename(file_or_path.filename)
            client.upload_fileobj(file_or_path, bucket_name, f'{prefix}/{secure_name}')
        
    except NoCredentialsError:
        print("Credentials not available")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

def put_file(files, prefix):
    """Upload files to Cloudflare R2 storage."""
    for file_key in files:
        file = files[file_key]  # Get the file from ImmutableMultiDict
        # Ensure the file is a FileStorage object before proceeding
        if isinstance(file, FileStorage):
            try:
                secure_name = secure_filename(file.filename)
                client.upload_fileobj(file, bucket_name, f'{prefix}/{secure_name}')
                print(f"File {secure_name} uploaded successfully.")
            except NoCredentialsError:
                print("Credentials not available")

def get_all_files(prefix):
    """List all files in Cloudflare R2 storage with a specific prefix."""
    
    try:
        response = client.list_objects_v2(Bucket=bucket_name, Prefix=prefix)
        files = []
        if 'Contents' in response:
            for obj in response['Contents']:
                files.append(obj['Key'])
        else:
            print("No 'Contents' found in response. Check if the prefix is correct and exists.")
        return files
    except NoCredentialsError:
        print("Credentials not available")
        return []
    except Exception as e:  # Catch-all for any other exceptions
        print(f"An unexpected error occurred: {e}")
        return []


def download_file(file_name, prefix, download_path='tmp'):
    """Download a specified file from Cloudflare R2 storage using download_fileobj."""

    try:
        key = f"{file_name}"
        # Check if the file exists
        
        client.head_object(Bucket=bucket_name, Key=key)
        download_path_full = os.path.join(download_path, file_name)
        os.makedirs(os.path.dirname(download_path_full), exist_ok=True)
        with open(download_path_full, 'wb') as f:
            client.download_fileobj(bucket_name, key, f)
        
        return download_path_full
    except client.exceptions.NoSuchKey:
        print(f"File {file_name} does not exist in the bucket.")
    except NoCredentialsError:
        print("Credentials not available")
    except FileNotFoundError:
        print(f"File {file_name} not found.")

# Example usage
# put_file('path/to/your/file.txt', 'your-prefix')
# download_file('file.txt', 'your-prefix')
