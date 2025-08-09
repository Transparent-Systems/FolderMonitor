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
Version: v1.0

This script contains utility static methods and classes
To import methods and class ensure utils.py is on the path.
For example:
# Add the scripts directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../scripts')))

Import methods or classes into a Python script with:
- import utils
- from utils import get_unique_logger, create_test_date, ProcessTestResult
"""

def get_unique_logger(log_level = "INFO") -> logging.Logger:
    """
    Create a unique logger instance with a name based on UUID import uuid
    """
    # Get globally unique logger name
    logger_name = f"Logger_{uuid.uuid4()}"
    logger = logging.getLogger(logger_name)
    
    # Set the logger to debug level initially for its internal setup messages.
    # The effective level will also be governed by the root logger's level.
    level_map = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL
    }
    logger.setLevel(level_map.get(log_level, logging.NOTSET)) # Use .get with default for robustness
    return logger



def create_test_data(path: str, files: list[str] | str):
    """
    Create files relative to path
    If files is empty then create folder
    """

    if isinstance(files, str):
        file_list = [f"{files}"]
    else:
        file_list = files

    # If file_list is empty then this is a folder
    if len(file_list) == 0:
        try:
            os.makedirs(path, exist_ok=True)
        except OSError as e:
            sys.exit(1)
        return path

    for filename in file_list:
        filename = filename.lstrip("/\\")
        file_path = os.path.join(path, filename)
        head = os.path.dirname(file_path)
        try:
            os.makedirs(name=head, exist_ok=True)
        except OSError as e:
            sys.exit(1)

        try:
            with open(file_path, 'w') as f:
                f.write(f"Test data for {file_path}\n")
        except Exception as e:
            sys.exit(1)

    return file_path


def delete_test_data(path: str, files: list[str] | str):
    """
    Delete files relative to path
    """

    if isinstance(files, str):
        file_list = [f"{files}"]
    else:
        file_list = files

    for filename in file_list:
        try:
            filename = filename.lstrip("/\\")
            filepath = os.path.join(path, filename)
            if (os.path.isfile(filepath)):
                os.remove(filepath)
            else:
                shutil.rmtree(path=filepath)
        except Exception as e:
            continue
    
    return filepath


class ProcessTestResult():
    """
    Class to store and retrieve test results
    """

    def __init__(self, testsuite_name: str):
        self.testsuite_name = testsuite_name
        self.success_count = 0
        self.failure_count = 0
        self.test_results: list[dict] = []
        self.start_time = time.perf_counter()
        self.test_time = self.start_time
        self.duration = 0
        self.test_counter = 0

    def process(self, test_case_name: str, test_ok: bool, test_output: str | list, test_step_name = ""):
        """
        Process test result.
        Calculates success and failure count and stores these metrics, result outputand identifiers in test_result
        The test results can be retrieved later on in method get_test_results
        """
        # --- Calculations
        end_time = time.perf_counter()
        test_duration = end_time - self.test_time
        self.test_time = end_time
        self.duration = end_time - self.start_time
        self.test_counter += 1
        
        if test_ok:
            self.success_count += 1
        else:
            self.failure_count += 1

        result_output_list = [str]

        if isinstance(test_output, str):
            result_output_list.append(test_output)
        else:
            result_output_list = test_output

        test_result = {
            "test_case_name" : test_case_name,
            "test_step_name" : test_step_name,
            "test_counter" : self.test_counter,
            "test_ok" : test_ok,
            "test_duration" : test_duration,
            "test_output" : result_output_list
        }
        self.test_results.append(test_result)

    def get_test_results(self) -> list[dict]:
        return (self.test_results)



class CheckPath():
    """
    Checks if a specific basename (file or folder) exists in a given remote path using rclone lsjson.

    Args:
        rclone_handler (RcloneHandler): An instance of the RcloneHandler.

    Returns:
        bool: True if the basename is present in remote path, False otherwise.
        list: If basename is present, a list of all files and folders present in remote path found so far.
            If basename is not present, a list of all files and folders present in remote path.
    """

    def __init__(self, rclone_handler: RcloneHandler, check_delay = 0):
        """
        Constructor

        Args:
            rclone_handler (RcloneHandler): An instance of the RcloneHandler.
            check_delay: optional delay timer for testing purposes only.
        """
        self.rclone_handler = rclone_handler
        self.check_delay = check_delay


    def basename_exists(self, parent_path: str, base_name: str) -> tuple[bool, bool, list]:
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
        rclone_command = [
            "lsjson",
            parent_path,
            "--max-depth", "1"
        ]

        (result_code, result_output) = self.rclone_handler.run_command(rclone_command)

        if result_code == 0 and result_output:
            try:
                json_output = json.loads(result_output)
                found_files = []
                for item in json_output:
                    # The 'Path' field in lsjson output is relative to the queried directory.
                    # For --max-depth 1, it will usually be just the filename.
                    item_path = item.get('Path')
                    item_isdir = item.get('IsDir')
                    if item_path:
                        found_files.append(item_path)
                        # Check if item is found and is a directory
                        if item_path == base_name:
                            if item_isdir:
                                return True, True, found_files  # Directory
                            else:
                                return True, False, found_files # File
                return False, False, found_files # File not found in the list
            except json.JSONDecodeError:
                return False, False, [f"Error: Could not decode JSON output: {result_output}"]
        elif result_code != 0:
            # If rclone itself returned an error (e.g., remote_path doesn't exist)
            return False, False, [f"Rclone command failed when listing '{parent_path}'."]
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
        rclone_command = [
            "lsjson",
            parent_path,
            "--max-depth", "1"
        ]

        (result_code, result_output) = self.rclone_handler.run_command(rclone_command)

        if result_code == 0 and result_output:
            try:
                json_output = json.loads(result_output)
                found_files = []
                for item in json_output:
                    # The 'Path' field in lsjson output is relative to the queried directory.
                    # For --max-depth 1, it will usually be just the filename.
                    item_path = item.get('Path')
                    item_isdir = item.get('IsDir')
                    if item_path:
                        found_files.append(item_path)
                        # Check if item is found and is a directory
                        if item_path == folder_name and item_isdir:
                            return True, found_files
                return False, found_files # File not found in the list
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
        rclone_command = [
            "lsjson",
            "--files-only",
            parent_path,
            "--max-depth", "1"
        ]

        (result_code, result_output) = self.rclone_handler.run_command(rclone_command)

        if result_code == 0 and result_output:
            try:
                json_output = json.loads(result_output)
                found_files = []
                for item in json_output:
                    # The 'Path' field in lsjson output is relative to the queried directory.
                    # For --max-depth 1, it will usually be just the filename.
                    item_path = item.get('Path')
                    if item_path:
                        found_files.append(item_path)
                        if item_path == file_name:
                            return True, found_files
                return False, found_files # File not found in the list
            except json.JSONDecodeError:
                return False, [f"Error: Could not decode JSON output: {result_output}"]
        elif result_code != 0:
            # If rclone itself returned an error (e.g., remote_path doesn't exist)
            return False, [f"Rclone command failed when listing '{parent_path}'."]
        else:
            # result_output is empty, meaning no files were found or directory is empty
            return False, []

