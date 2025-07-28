import json
import logging
import uuid
import os
import shutil
import logging
import time
from rclone_handler import RcloneHandler


def get_unique_logger(log_level = "INFO") -> logging.Logger:
    """
    # Create a unique logger instance with a name based on UUID import uuid
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
    """

    if isinstance(files, str):
        file_list = [f"{files}"]
    else:
        file_list = files

    for filename in file_list:
        filename = filename.lstrip("/\\")
        filepath = os.path.join(path, filename)
        head = os.path.dirname(filepath)
        try:
            os.makedirs(head, exist_ok=True)
        except OSError as e:
            sys.exit(1)

        try:
            with open(filepath, 'w') as f:
                f.write(f"Test data for {filepath}\n")
        except Exception as e:
            sys.exit(1)

    return filepath


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
    Class to store and retrive test results
    """

    def __init__(self, testsuite_name: str):
        self.testsuite_name = testsuite_name
        self.success_count = 0
        self.failure_count = 0
        self.test_results = []
        self.start_time = time.perf_counter()
        self.duration = 0

    def process_result(self, testname: str, test_ok: bool, result_output: str | list, test_details = ""):
        if len(test_details) == 0:        
            description = testname
        else:
            description = f"{testname} - {test_details}"

        if test_ok:
            self.success_count += 1
            self.test_results.append(f"success    | {description}")
        else:
            self.failure_count += 1
            self.test_results.append(f"failure    | {description}")

            if isinstance(result_output, str):
                self.test_results.append(f"{" " * 10} | {result_output}")
            else:
                for item in result_output:
                    self.test_results.append(f"{" " * 10} | {item}")

        # --- Calculate duration so far.
        end_time = time.perf_counter()
        self.duration = end_time - self.start_time

    def get_result(self):
        return (self.testsuite_name, self.success_count, self.failure_count, self.test_results, self.duration)



def check_basename_in_path(rclone_handler: RcloneHandler, remote_path: str, basename: str) -> tuple[bool, list]:
    """
    Checks if a specific basename (file or folder) exists in a given remote path using rclone lsjson.

    Args:
        rclone_handler (RcloneHandler): An instance of the RcloneHandler.
        remote_path (str): The remote path (e.g., 'e2:test-foldermonitor/some/folder').
                            This should be the folder containing filename
        basename (str): The name of a file or folder to check for (e.g., 'test999.txt', or 'Subfolder1').

    Returns:
        bool: True if the basename is present in remote path, False otherwise.
        list: If basename is present, a list of all files and folders present in remote path found so far.
              If basename is not present, a list of all files and folders present in remote path.
    """
    # Construct the rclone lsjson command
    rclone_command = [
        "lsjson",
        remote_path,
        "--files-only",
        "--max-depth", "1"
    ]

    (result_code, result_output) = rclone_handler.run_command(rclone_command)

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
                    if item_path == basename:
                        return True, found_files
            return False, found_files # File not found in the list
        except json.JSONDecodeError:
            return False, [f"Error: Could not decode JSON output: {result_output}"]
    elif result_code != 0:
        # If rclone itself returned an error (e.g., remote_path doesn't exist)
        return False, [f"Rclone command failed when listing '{remote_path}'."]
    else:
        # result_output is empty, meaning no files were found or directory is empty
        return False, []

