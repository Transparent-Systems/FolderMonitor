import logging
import boto3
from botocore.exceptions import BotoCoreError, ClientError
from scripts.profile_handler import ProfileHandler

class S3Factory:
    def __init__(self, logger : logging.Logger = None,
                app_name="foldermonitor"):
        """
        Docstring for __init__
        
        :param self: this instance
        :param logger: logger
        :type logger: logging.Logger
        :param app_name: The name of the application. This is required for ProfileHandler
        :type app_name: str
        """
        self.logger = logger or logging.getLogger(__name__)
        # Create instance of ProfileHandler
        self.profile_handler = ProfileHandler(
            logger=self.logger,
            app_name=app_name
            )

    def get_client_from_remote(self, profile_name: str) -> boto3.client:
        """
        Docstring for get_client_from_remote
        
        :param self: instance of this class
        :param profile_name: the name of the profile to use. The remote profile is stored in the config file of the application.
        :type profile_name: str
        :return: boto3 client
        :rtype: Any
        """
        profile = self.profile_handler.get_profile(profile_name=profile_name)
        if not profile:
            raise KeyError(f"Profile '{profile_name}' not found in {self.profile_handler.config_path}")

        # Create the boto3 client
        s3_endpoint = profile.get('s3_endpoint')
        # Check if "http://" inside s3_endpoint
        if 'http://' in s3_endpoint:
            s3_endpoint = s3_endpoint.replace('http://', 'https://')

        # Check if "https://" inside s3_endpoint
        if 'https://' not in s3_endpoint:
            s3_endpoint_url = f"https://{s3_endpoint}"
        else:
            s3_endpoint_url = s3_endpoint
        
        s3_access_key_id = profile.get('s3_access_key_id')
        s3_access_key_secret = profile.get('s3_access_key_secret')

        client = boto3.client(
            's3',
            aws_access_key_id=s3_access_key_id,
            aws_secret_access_key=s3_access_key_secret,
            endpoint_url=s3_endpoint_url,
            # Optional: Add retry config for better performance/reliability
            config=boto3.session.Config(retries={'max_attempts': 3, 'mode': 'standard'})
        )

        return client

# --- Example Usage ---
if __name__ == "__main__":
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    factory = S3Factory(
        logger=logger,
        app_name="foldermonitor"
    )

    profile_name = "idrive-test"
    
    try:
        s3_client = factory.get_client_from_remote(profile_name=profile_name)
        
        # Quick check if there are any files in bucket with path prefix
        # Get a maximum of 10 keys !
        bucket = "test-foldermonitor"
        prefix = "idrive-cloud-storage"
        response = s3_client.list_objects_v2(Bucket=bucket, Prefix=prefix, MaxKeys=10)
        key_count = response.get('KeyCount', 0)
        print(f"Connected to {profile_name}:{bucket}. Objects found: {key_count}")
        
    except Exception as e:
        print(f"Error: {e}")
        