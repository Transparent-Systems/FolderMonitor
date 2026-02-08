"""
s3_handler.py
Author: John Zoetebier
Date: 2026-01-27

Description:
    This script implements the S3Handler class, which provides functionality
    to copy or delete files and folders using boto3 for S3 compatible storage providers.

Requirements:
- boto3 must be installed.
- S3 credentials and configuration should be set via environment variables
  (access_key_id, secret_access_key, S3_DEFAULT_REGION) or ~/.aws/ files.
- For non-S3 compatible providers, set endpoint_url environment variable.

See: 
    https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3.html
    https://boto3.amazonaws.com/v1/documentation/api/latest/guide/quickstart.html
"""

import logging
import hashlib
import os
from pathlib import Path
from typing import Tuple, List

try:
    import boto3
except ImportError:
    print("boto3 not found. Please install it using 'pip install boto3'")
    boto3 = None

from botocore.exceptions import ClientError
from boto3.s3.transfer import TransferConfig

try:
    from s3_factory import S3Factory
except ModuleNotFoundError:
    from scripts.s3_factory import S3Factory

try:
    from scripts.base_handler import BaseHandler
except ModuleNotFoundError:
    from base_handler import BaseHandler


class S3Handler(BaseHandler):
    """
    A class to copy or delete files and folders using boto3 for S3 compatible storage.
    Mimics RcloneHandler structure.
    """

    def __init__(
        self,
        logger: logging.Logger,
        base_source_path: str,
        base_remote_path: str,
        remote_profile: str,
        app_name: str = "foldermonitor",
    ):
        """
        base_remote_path      : profile:bucket/prefix (e.g., "e2:mybucket/backups")
        base_source_path      : local source path
        remote_profile        : profile name (e.g., "e2")
        logger                : logger instance
        app_name              : application name (e.g., "foldermonitor")
        """
        self.logger = logger
        self.base_remote_path = Path(base_remote_path)
        self.base_source_path = Path(base_source_path)
        self.profile_name = remote_profile
        self.app_name = app_name
    
        """
        Initializes the client once for the lifetime of the monitor.
        """
        # Get client fusing S3ConnectionFactory
        s3_factory = S3Factory(
            logger=self.logger,
            app_name=app_name
            )
        self.client = s3_factory.get_client_from_remote(profile_name=remote_profile)

        # high_performance_transfer_config = TransferConfig(
        #     # The file size at which to start using multipart uploads
        #     multipart_threshold=25 * 1024 * 1024,  # 25MB
            
        #     # The size of each chunk
        #     multipart_chunksize=10 * 1024 * 1024,  # 10MB
            
        #     # The maximum number of concurrent threads to use
        #     max_concurrency=10,
            
        #     # Use threads to improve speed
        #     use_threads=True,
            
        #     # If the transfer fails, how many times to retry the specific chunk
        #     num_download_attempts=5
        #     )

        reliable_performance_transfer_config = TransferConfig(
            # The file size at which to start using multipart uploads
            multipart_threshold=25 * 1024 * 1024,  # 25MB
            
            # The size of each chunk
            multipart_chunksize=5 * 1024 * 1024,  # 5MB
            
            # The maximum number of concurrent threads to use
            max_concurrency=4,
            
            # Use threads to improve speed
            use_threads=True,
            
            # If the transfer fails, how many times to retry the specific chunk
            num_download_attempts=10
            )

        # We may make the transfer config configurable in the future
        self.transfer_config = reliable_performance_transfer_config


    def _get_bucket_and_key(self, full_path: str) -> Tuple[str, str]:
        """
        Splits a full path (e.g., "bucket/prefix/file.txt") into bucket and key.
        """
        # Ensure forward slashes
        full_path = full_path.replace("\\", "/")
        # Strip the storage identifier, the part till the first colon
        full_path = full_path.split(':', 1)[1] if ':' in full_path else full_path
        parts = full_path.split('/', 1)
        bucket = parts[0]
        key = parts[1] if len(parts) > 1 else ""
        return bucket, key

    def _list_objects(self, bucket, prefix) -> List[dict]:
        """Helper to list all objects with prefix"""
        objects = []
        paginator = self.client.get_paginator('list_objects_v2')
        try:
            for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
                if 'Contents' in page:
                    objects.extend(page['Contents'])
        except Exception as e:
            self.logger.error(f"Error listing objects: {e}")
        return objects

    def _calculate_md5(self, file_path: str) -> str:
        """Calculates the MD5 hash of a file."""
        hash_md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()

    def get_remote_path(self, source_path: str) -> str:
        """
        Derives remote path from base source path and this source path.
        Returns a string path (bucket/prefix/...). 
        """
        source_path_obj = Path(source_path)
        try:
            relative_path = source_path_obj.relative_to(self.base_source_path)
        except ValueError:
            # Fallback if path is not relative to base_source_path
            relative_path = Path(source_path).name
        
        remote_path = self.base_remote_path / relative_path
        return remote_path.as_posix()

  
    def file_exists(self, remote_path: str) -> Tuple[int, str]:
        """
        Check if remote path exists
        """
        bucket, key = self._get_bucket_and_key(remote_path)
        
        try:
            self.logger.debug(f"Check if path exists: s3://{bucket}/{key}")
            self.client.head_object(Bucket=bucket, Key=key)
            return (0, "")
        except Exception as e:
            self.logger.debug(f"Path does not exist: s3://{bucket}/{key}")
            return (1, str(e))

    def copy_file(self, source_path, remote_path=None) -> tuple[int, list[str]]:
        """
        Copy source_path to remote_path.
        If remote_path is None, the remote_path is derived from the source_path
        Returns:
            (result_code, result_output)
        """

        if remote_path is None:
            remote_path = self.get_remote_path(source_path=source_path)

        bucket, key = self._get_bucket_and_key(remote_path)
        
        # Get file modification time to store as metadata
        mtime = str(int(Path(source_path).stat().st_mtime))
        extra_args = {'Metadata': {'mtime': mtime}}

        # Get metadata of obect bucket and prefix
        try:
            head_object = self.client.head_object(Bucket=bucket, Key=key)
            size = head_object['ContentLength']
            etag = head_object['ETag'].strip('"')
            meta_data = head_object['Metadata']
            mtime = meta_data['mtime']

            # We may have stored mtime in metadata during a previous upload
            # However mtime could be absent, so check if it exiists first
            if mtime and mtime == str(int(Path(source_path).stat().st_mtime)):
                return (0, "")

            # Is size and etag same as source file, then  return
            if size == Path(source_path).stat().st_size:
                md5 = self._calculate_md5(source_path)
                if etag == md5:
                    return (0, "")
            else:
                pass
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                pass
               
        try:
            self.logger.debug(f"Uploading {source_path} to s3://{bucket}/{key}")
            self.client.upload_file(source_path, bucket, key, ExtraArgs=extra_args, Config=self.transfer_config)
            return (0, "")
        except Exception as e:
            self.logger.error(f"Error uploading file {source_path}: {e}")
            return (1, str(e))

    def copy_folder(self, source_path) -> Tuple[int, str]:
        """
        Copy the source path to the derived remote path.
        """
        source_path_obj = Path(source_path)
        if not source_path_obj.exists():
            return (1, f"Source path {source_path} does not exist")

        remote_path = self.get_remote_path(source_path=source_path)
        bucket, prefix = self._get_bucket_and_key(remote_path)
        if prefix and not prefix.endswith('/'):
            prefix += '/'

        # List all objects in the remote folder to avoid checking each file individually
        remote_objects = self._list_objects(bucket, prefix)
        # Create a dictionary for faster lookup: key -> object
        remote_objects_map = {obj['Key']: obj for obj in remote_objects}

        errors = []
        # Walk through the source directory
        for root, dirs, files in os.walk(source_path):
            for file in files:
                local_file_path = Path(root) / file
                
                # Calculate relative path to construct the key
                try:
                    relative_path = local_file_path.relative_to(source_path_obj)
                except ValueError:
                    relative_path = local_file_path.name
                
                # S3 keys use forward slashes
                key = f"{prefix}{relative_path.as_posix()}"
                
                should_copy = False
                
                if key not in remote_objects_map:
                    should_copy = True
                else:
                    remote_obj = remote_objects_map[key]
                    local_size = local_file_path.stat().st_size
                    remote_size = remote_obj['Size']
                    remote_etag = remote_obj.get('ETag', '').strip('"')
                    
                    # If file size is equal, check ETag (MD5)
                    if local_size == remote_size:
                        # If ETag contains '-', it is a multipart upload and cannot be verified by simple MD5
                        if '-' not in remote_etag:
                            local_md5 = self._calculate_md5(str(local_file_path))
                            if local_md5 != remote_etag:
                                should_copy = True
                            else:
                                should_copy = False
                        else:
                            # Fallback for multipart files: assume size match is enough
                            should_copy = False
                    else:
                        should_copy = True

                if should_copy:
                    ret, msg = self.copy_file(str(local_file_path))
                    if ret != 0:
                        errors.append(msg)
                else:
                    self.logger.debug(f"Skipping {local_file_path} (metadata match)")
        
        if errors:
            return (1, "\n".join(errors))
        return (0, "")

    def delete_file(self, remote_path) -> Tuple[int, str]:
        """
        Delete file at remote_path.
        remote_path should be the full path returned by get_remote_path.
        """
        bucket, key = self._get_bucket_and_key(remote_path)
        try:
            self.logger.debug(f"Deleting s3://{bucket}/{key}")
            self.client.delete_object(Bucket=bucket, Key=key)
            return (0, "")
        except Exception as e:
            self.logger.error(f"Error deleting file {remote_path}: {e}")
            return (1, str(e))

    def delete_folder(self, remote_path) -> Tuple[int, str]:
        """
        Delete objects in remote_path
        This is done in batches to reduce the number of requests.
        """
        bucket, prefix = self._get_bucket_and_key(remote_path)
        # Ensure prefix ends with / to avoid deleting partial matches of other folders if named similarly
        if prefix and not prefix.endswith('/'):
            prefix += '/'

        try:
            objects = self._list_objects(bucket, prefix)
            if not objects:
                return (0, "")

            # Delete in batches of 1000 (S3 limit)
            delete_keys = [{'Key': obj['Key']} for obj in objects]
            
            # Simple batching
            batch_size = 1000
            for i in range(0, len(delete_keys), batch_size):
                batch = delete_keys[i:i+batch_size]
                self.logger.debug(f"Deleting batch of {len(batch)} objects from {bucket}")
                response = self.client.delete_objects(Bucket=bucket, Delete={'Objects': batch})
            
            return (0, response)
        except Exception as e:
            self.logger.error(f"Error deleting folder {remote_path}: {e}")
            return (1, str(e))

    def sync_folder(self, source_path) -> Tuple[int, str]:
        """
        Sync the source path to the derived remote path.
        Make remote path identical to source path.
        """
        # 1. Copy (Upload) all files from source
        copy_ret, copy_msg = self.copy_folder(source_path)
        if copy_ret != 0:
            return (copy_ret, copy_msg)

        # 2. Delete files in remote that are NOT in source
        remote_path = self.get_remote_path(source_path)
        bucket, prefix = self._get_bucket_and_key(remote_path)
        if prefix and not prefix.endswith('/'):
            prefix += '/'

        try:
            remote_objects = self._list_objects(bucket, prefix)
            
            # Build set of expected keys from source
            expected_keys = set()
            source_path_obj = Path(source_path)
            for root, dirs, files in os.walk(source_path):
                for file in files:
                    local_file = Path(root) / file
                    # Calculate relative path from source root
                    rel_path = local_file.relative_to(source_path_obj)
                    # Key is prefix + rel_path (normalized to forward slashes)
                    key = f"{prefix}{rel_path.as_posix()}"
                    expected_keys.add(key)

            # Identify objects to delete
            to_delete = []
            for obj in remote_objects:
                if obj['Key'] not in expected_keys:
                    to_delete.append({'Key': obj['Key']})
            
            if to_delete:
                self.logger.info(f"Sync: Deleting {len(to_delete)} extraneous files from remote.")
                # Delete in batches
                batch_size = 1000
                for i in range(0, len(to_delete), batch_size):
                    batch = to_delete[i:i+batch_size]
                    self.client.delete_objects(Bucket=bucket, Delete={'Objects': batch})

            return (0, "")

        except Exception as e:
            self.logger.error(f"Error during sync cleanup: {e}")
            return (1, str(e))