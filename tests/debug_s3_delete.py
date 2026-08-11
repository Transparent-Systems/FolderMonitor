
from pathlib import Path
import sys
import boto3
import logging

# Add the scripts directory to the Python path
scriptspath = Path(__file__).parent / Path("../scripts")
sys.path.insert(0, scriptspath.resolve().as_posix())
from profile_handler import ProfileHandler

# Config from foldermonitor.conf in local user path
profile_handler = ProfileHandler(app_names="foldermonitor")
profile_name = "idrive-test"
profile_attributes = profile_handler.get_profile(profile_name=profile_name)

ACCESS_KEY = profile_attributes.get('access_key_id')
SECRET_KEY = profile_attributes.get('access_key_secret')
ENDPOINT = profile_attributes.get('endpoint')

endpoint_url = ENDPOINT
if ("http://" in endpoint_url):
    endpoint_url = endpoint_url.replace("http://", "https://")
if ("https://" not in endpoint_url):
    endpoint_url = f"https://{endpoint_url}"

SECRET_KEY = profile_attributes.get('access_key_secret')
BUCKET = "test-foldermonitor"
PREFIX = "idrive-cloud-storage/test-s3-handler-integration/"

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("debug_s3")

def main():
    s3 = boto3.client(
        's3',
        aws_access_key_id=ACCESS_KEY,
        aws_secret_access_key=SECRET_KEY,
        endpoint_url=endpoint_url
    )

    print(f"Listing objects in Bucket: {BUCKET}, Prefix: {PREFIX}")
    try:
        response = s3.list_objects_v2(Bucket=BUCKET, Prefix=PREFIX)
    except Exception as e:
        print(f"Error listing: {e}")
        return

    if 'Contents' not in response:
        print("No objects found.")
        return

    objects = response['Contents']
    print(f"Found {len(objects)} objects:")
    for obj in objects:
        print(f" - {obj['Key']}")

    # Pick one to delete
    target_key = objects[0]['Key']
    print(f"\nAttempting to delete: {target_key}")

    # Method 1: delete_objects (Batch) - This is what delete_folder uses
    delete_payload = {'Objects': [{'Key': target_key}]}
    print(f"Calling delete_objects with payload: {delete_payload}")
    
    try:
        del_resp = s3.delete_objects(Bucket=BUCKET, Delete=delete_payload)
        print("Delete Response:")
        print(del_resp)
    except Exception as e:
        print(f"Error deleting: {e}")

    # Verify
    print(f"\nVerifying existence of Bucket: {BUCKET}, Key: {target_key}")
    try:
        # head_object throws 404 if not found
        s3.head_object(Bucket=BUCKET, Key=target_key)
        print("!!! Object STILL EXISTS !!!")
    except Exception as e:
        print(f"Object check result: {e}")
        if "404" in str(e):
            print("Object is gone (Success).")

if __name__ == "__main__":
    main()
