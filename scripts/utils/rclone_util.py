import json
import logging
import uuid
import os
import shutil
import logging
import time
import sys
from rclone_handler import RcloneHandler

"""
This script contains utility static methods and classes for rclone
"""


class CheckPath:
    """
    Checks if a specific basename (file or folder) exists in a given remote path using rclone lsjson.

    Args:
        rclone_handler (RcloneHandler): An instance of the RcloneHandler.

    Returns:
        bool: True if the basename is present in remote path, False otherwise.
        list: If basename is present, a list of all files and folders present in remote path found so far.
            If basename is not present, a list of all files and folders present in remote path.
    """

    def __init__(self, rclone_handler: RcloneHandler, check_delay=0):
        """
        Constructor

        Args:
            rclone_handler (RcloneHandler): An instance of the RcloneHandler.
            check_delay: optional delay timer for testing purposes only.
        """
        self.rclone_handler = rclone_handler
        self.check_delay = check_delay

    def basename_exists(
        self, parent_path: str, base_name: str
    ) -> tuple[bool, bool, list]:
        """Check if folder exists.

        Args:
            parent_path (str): folder containing base_name
            base_name (str): the base_name we check to exist

        Returns:
            tuple (bool, bool, list): A tuple indicating if the base_name exists, if it is a directory and a list of some data.
                                      The list of data can contain a list of files / folders or an error message
        """

        time.sleep(self.check_delay)  # Sleep before checking

        # Construct the rclone lsjson command
        rclone_command = ["lsjson", parent_path, "--max-depth", "1"]

        (result_code, result_output) = self.rclone_handler.run_command(rclone_command)

        if result_code == 0 and result_output:
            try:
                json_output = json.loads(result_output)
                found_files = []
                for item in json_output:
                    # The 'Path' field in lsjson output is relative to the queried directory.
                    # For --max-depth 1, it will usually be just the filename.
                    item_path = item.get("Path")
                    item_isdir = item.get("IsDir")
                    if item_path:
                        found_files.append(item_path)
                        # Check if item is found and is a directory
                        if item_path == base_name:
                            if item_isdir:
                                return True, True, found_files  # Directory
                            else:
                                return True, False, found_files  # File
                return False, False, found_files  # File not found in the list
            except json.JSONDecodeError:
                return (
                    False,
                    False,
                    [f"Error: Could not decode JSON output: {result_output}"],
                )
        elif result_code != 0:
            # If rclone itself returned an error (e.g., remote_path doesn't exist)
            return (
                False,
                False,
                [f"Rclone command failed when listing '{parent_path}'."],
            )
        else:
            # result_output is empty, meaning no files were found or directory is empty
            return False, False, []

    def folder_exists(self, parent_path: str, folder_name: str) -> tuple[bool, list]:
        """Check if folder exists.

        Args:
            parent_path (str): parent folder containing folder_name
            folder_name (str): the folder we check to exist

        Returns:
            tuple (bool, list): A tuple indicating if the folder exists and a list of some data.
        """

        time.sleep(self.check_delay)  # Sleep before checking

        # Construct the rclone lsjson command
        rclone_command = ["lsjson", parent_path, "--max-depth", "1"]

        (result_code, result_output) = self.rclone_handler.run_command(rclone_command)

        if result_code == 0 and result_output:
            try:
                json_output = json.loads(result_output)
                found_files = []
                for item in json_output:
                    # The 'Path' field in lsjson output is relative to the queried directory.
                    # For --max-depth 1, it will usually be just the filename.
                    item_path = item.get("Path")
                    item_isdir = item.get("IsDir")
                    if item_path:
                        found_files.append(item_path)
                        # Check if item is found and is a directory
                        if item_path == folder_name and item_isdir:
                            return True, found_files
                return False, found_files  # File not found in the list
            except json.JSONDecodeError:
                return False, [f"Error: Could not decode JSON output: {result_output}"]
        elif result_code != 0:
            # If rclone itself returned an error (e.g., remote_path doesn't exist)
            return False, [f"Rclone command failed when listing '{parent_path}'."]
        else:
            # result_output is empty, meaning no files were found or directory is empty
            return False, []

    def file_exists(self, parent_path: str, file_name: str) -> tuple[bool, list]:
        """Check if file file_name exists in folder folder_path.

        Args:
            parent_path (str): folder containing file_name
            file_name (str): the filde we check to exist

        Returns:
            tuple (bool, list): A tuple indicating if the ffile exists and a list of some data.
        """

        time.sleep(self.check_delay)  # Sleep before checking
        # Construct the rclone lsjson command
        rclone_command = ["lsjson", "--files-only", parent_path, "--max-depth", "1"]

        (result_code, result_output) = self.rclone_handler.run_command(rclone_command)

        if result_code == 0 and result_output:
            try:
                json_output = json.loads(result_output)
                found_files = []
                for item in json_output:
                    # The 'Path' field in lsjson output is relative to the queried directory.
                    # For --max-depth 1, it will usually be just the filename.
                    item_path = item.get("Path")
                    if item_path:
                        found_files.append(item_path)
                        if item_path == file_name:
                            return True, found_files
                return False, found_files  # File not found in the list
            except json.JSONDecodeError:
                return False, [f"Error: Could not decode JSON output: {result_output}"]
        elif result_code != 0:
            # If rclone itself returned an error (e.g., remote_path doesn't exist)
            return False, [f"Rclone command failed when listing '{parent_path}'."]
        else:
            # result_output is empty, meaning no files were found or directory is empty
            return False, []
