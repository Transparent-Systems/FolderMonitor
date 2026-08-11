import logging
import boto3
from typing import Any, TYPE_CHECKING
from botocore.client import Config
if TYPE_CHECKING:
    from mypy_boto3_s3.client import S3Client

class S3Factory:
    def __init__(self, logger : logging.Logger
                ):
        """
        Docstring for __init__
        
        :param self: this instance
        :param logger: logger
        :type logger: logging.Logger
        :param app_name: The name of the application. This is required for ProfileHandler
        :type app_name: str
        """
        self.logger = logger or logging.getLogger(__name__)

    def _log_retry_events(self, **kwargs):
        """Callback function to log internal boto3 retries."""
        # Pull the response out of the keyword arguments safely
        response = kwargs.get('response')
        error_code = 'Unknown'
        
        if response and isinstance(response, tuple):
            # response is (http_response, parsed_data)
            _, parsed_data = response
            if isinstance(parsed_data, dict):
                error_info = parsed_data.get('Error', {})
                error_code = error_info.get('Code', 'Unknown')
        elif 'caught_exception' in kwargs:
            error_code = type(kwargs['caught_exception']).__name__
            
        if error_code != 'Unknown':
            if error_code in ['SlowDown', 'Throttling', 'RequestLimitExceeded']:
                self.logger.warning(f"(!) THROTTLED: IDrive/S3 requested a backoff. Code: {error_code}")
            else:
                # Filter out error_code 404 : file not found
                if error_code != '404':
                    self.logger.debug(f"Retrying S3 request due to: {error_code}")

    def get_s3_client(self, profile_config: dict) -> "S3Client":
        """
        Docstring for get_s3_client
        
        :param self: instance of this class
        :param profile_config: Profile configuration to use.
        :type profile_name: str
        :return: boto3 client
        :rtype: Any
        """

        # Get endpoint
        endpoint = profile_config.get('endpoint', "")
        # For AWS the endpoint can be derived from the region
        if not endpoint:
            region = profile_config.get('region')
            endpoint = f"s3.{region}.amazonaws.com"

        # Check if "http://" inside endpoint
        if 'http://' in endpoint:
            endpoint = endpoint.replace('http://', 'https://')

        # Check if "https://" inside endpoint
        if 'https://' in endpoint:
            endpoint_url = endpoint
        else:
            endpoint_url = f"https://{endpoint}"
        
        access_key_id = profile_config.get('access_key_id')
        access_key_secret = profile_config.get('access_key_secret')
        region = profile_config.get('region')
        provider_name = profile_config.get('provider_name')

        # Define common client settings once
        common_config = Config(
            retries={'max_attempts': 3, 'mode': 'standard'},
            # Optional: connect_timeout and read_timeout can be added here for extra reliability
            connect_timeout=5, 
            read_timeout=10
        )

        # On AWS we can omit the endpoint_url and use the reqion only

        if provider_name and " aws " in provider_name.lower():
            self.logger.debug("Provider is AWS")
            client = boto3.client(
                service_name='s3',
                aws_access_key_id=access_key_id,
                aws_secret_access_key=access_key_secret,
                region_name=region,
                config=common_config
                )
        else:
            # For Cloudflare R2, ensure region is set to 'auto' if missing
            if provider_name and 'cloudflare' in provider_name.lower() and not region:
                region = 'auto'

            client = boto3.client(
                service_name='s3',
                aws_access_key_id=access_key_id,
                aws_secret_access_key=access_key_secret,
                endpoint_url=endpoint_url,
                region_name=region,
                config=common_config
            )

        # Access the internal event system
        event_system = client.meta.events
        # Register the logger to the 'needs-retry' event
        # This event fires whenever boto3 decides to retry a request
        event_system.register('needs-retry.s3.*', self._log_retry_events)
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
        logger=logger
    )

    profile_name = "s3-test"
    # Get profile
    from sqlite_handler import SQLiteHandler
    sqlite_handler = SQLiteHandler(
        logger=logger,
        db_path="tests/data/foldermonitor.sqlite"
    )
    profile = sqlite_handler.get_profile(profile_name=profile_name)
    if profile is None:
        print(f"Profile {profile_name} not found")
        exit(1)

    profile_config = profile.get("config", {})
    print(f"Profile config: {profile_config}")
             
    try:
        s3_client = factory.get_s3_client(profile_config=profile_config)
        
        # Quick check if there are any files in bucket with path prefix
        # Get a maximum of 10 keys !
        bucket = "test-foldermonitor"
        prefix = "idrive-cloud-storage"
        response = s3_client.list_objects_v2(Bucket=bucket, Prefix=prefix, MaxKeys=10)
        key_count = response.get('KeyCount', 0)
        print(f"Connected to {profile_name}:{bucket}. Objects found: {key_count}")
        
    except Exception as e:
        print(f"Error: {e}")
