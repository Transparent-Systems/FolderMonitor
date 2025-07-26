"""
This script makes changes to the monitor_path to trigger events in the MonitorHandler
The script depens on a folder_monitor running.
folder_monitor runs in a separate script
When folder_monitor would be started in this script there could be thread racing conditions that would affect the test results
In addition: we want to test a running file_monitor not monitor_handler
Pre-requisites:
Start folder_monitor using the same monitor yaml file as this script
    From the application folder run:
    python.exe .\scripts\folder_monitor.py --monitor-config-path tests/conf/monitor.yaml

Important notes:
1)
This relates to testing s3-compatible cloud storage.
S3 storage (or compatible versions like IDrive e2) is an object storage system. It does not have a real foldr structure.
Now, when in a tree with just 1 fie that file is deleted, the entire folder tree is gone!
For example: e2:mybucket/a/b/c/test1.txt
After deleting test1.txt, the only thing remaining is: e2:mybucket
2)
The behaviour for a file like "rclone ls <file>" is different between local storage and remote storage.
To get a more reliable check if a file exists on both local and remote storage use "rclone json <parent-folder>

"""

import argparse
import json
import logging.handlers
import os
import sys
import logging
import shutil
import time
import yaml

# Add the scripts directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../scripts')))

from rclone_handler import RcloneHandler
from utils import create_test_data, delete_test_data, get_unique_logger, get_destination_path


class ProcessTestResult():

    def __init__(self, monitor_name: str):
        self.monitor_name = monitor_name
        self.success_count = 0
        self.failure_count = 0
        self.test_results = []

    def process_result(self, testname: str, ok: bool, result_output: str | list):
        # Declare which variables are global
        if ok:
            self.success_count += 1
            self.test_results.append(f"success  | {testname}")
        else:
            self.failure_count += 1
            self.test_results.append(f"failure  | {testname} | failure")

        if isinstance(result_output, str):
            self.test_results.append(f"         | {result_output}")
        else:
            for item in result_output:
                self.test_results.append(f"         | {item}")


    def get_result(self):
        return (self.monitor_name, self.success_count, self.failure_count, self.test_results)


def check_file_exists_rclone_lsjson(rclone_handler, remote_path, filename):
    """
    Checks if a specific file exists in a given remote path using rclone lsjson.

    Args:
        rclone_handler (RcloneHandler): An instance of the RcloneHandler.
        remote_path (str): The remote path (e.g., 'e2:test-foldermonitor/some/folder').
        filename (str): The name of the file to check for (e.g., 'test999.txt').

    Returns:
        bool: True if the file exists, False otherwise.
        list: A list of the full paths of found files, if any.
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
                    if item_path == filename:
                        return True, found_files
            return False, found_files # File not found in the list
        except json.JSONDecodeError:
            logger.debug(f"Error: Could not decode JSON output: {result_output}")
            return False, []
    elif result_code != 0:
        # If rclone itself returned an error (e.g., remote_path doesn't exist)
        logger.debug(f"Rclone command failed when listing '{remote_path}'.")
        return False, []
    else:
        # result_output is empty, meaning no files were found or directory is empty
        return False, []


def run_integration_check(monitor_name: str, src_path = "data/Source",destination_path = "data/Destination", base_path = "", logger = None, test_delay=1):
    """
    Trigger events in monitor path src_path
    All files and folder created will be in test subfolder
    That way we can safely remove that test subfolder from source and destination
    """
    logger.debug("--- Rclone Integration Check ---")
    test_src_path = os.path.join(src_path, "test_folder_monitor_integration")

    # Create rclone_handler to check files at destination_path
    rclone_handler = RcloneHandler(destination_path=destination_path, base_path=base_path, logger=logger, rclone_flags='')
    process_test_result = ProcessTestResult(monitor_name)
    logger.debug(f"Starting tests for monitor name [{monitor_name}] on monitor path [{src_path}]...")

    try:
        testname = "Test 1 : Create new file"
        filename = "Subfolder1/test1.txt"
        filepath = create_test_data(path=test_src_path, files=filename)
        time.sleep(test_delay)  # Sleep for a short duration
        dst_path = get_destination_path(path=os.path.dirname(filepath), base_path=base_path, root_destination_path=destination_path)
        (found, files) = check_file_exists_rclone_lsjson(rclone_handler, remote_path=dst_path, filename=os.path.basename(filename))
        process_test_result.process_result(testname, found, files)
    
        testname = "Test 2 : Delete a file"
        filename = "Subfolder1/test1.txt"
        filepath = delete_test_data(path=test_src_path, files=filename)
        logger.debug(f"Deleted source file : '{filepath}'")
        time.sleep(test_delay)  # Sleep for a short duration
        dst_path = get_destination_path(path=os.path.dirname(filepath), base_path=base_path, root_destination_path=destination_path)
        (found, files) = check_file_exists_rclone_lsjson(rclone_handler, remote_path=dst_path, filename=os.path.basename(filename))
        process_test_result.process_result(testname, (not found and "test1.txt" not in files), files)

        # testname = "Test 1 : Create subfolder with files. Check last file only"
        # logger.debug(f"Creating files")
        # filename = "Subfolder2/test1.txt"
        # filepath = create_test_data(path=test_src_path, files=filename)
        # filename = "Subfolder2/test2.txt"
        # filepath = create_test_data(path=test_src_path, files=filename)
        # # Wait to let monitor finish
        # time.sleep(test_delay)  # Sleep for a short duration to avoid busy-waiting
        # dst_path = get_destination_path(path=filepath, base_path=base_path, root_destination_path=destination_path)
        # rclone_command = ["lsf", "--format", "tshp", "--separator", " | ", dst_path] 
        # (result_code, result_output) = rclone_handler.run_command(rclone_command)
        # logger.debug(f"Check if file '{dst_path}' been created:\n{result_output}")
        # process_test_result.process_result(testname, result_code == 0, result_output)

        # # Test 6: Emulate move file
        # logger.debug("Move file ...")
        # old_filepath = create_test_data(src_path, ["Subfolder1/test3.txt"])
        # shutil.move(f"{src_path}/Subfolder1/test3.txt", f"{src_path}/Subfolder1/test3_moved.txt") 
        # # Delete old file at destination
        # (result_code, result_output) = handler.delete_file(old_filepath)
        # assert result_code == 0  


    except Exception as e:
        logger.debug(f"\n--- Integration check for {monitor_name} FAILED: {e} ---")
        process_test_result.process_result(testname, False , f"Fatal error executing tests: {e}")
    finally:
        logger.debug(f"\n--- Integration check cleanup for {monitor_name}")

    return process_test_result
   
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="This script runs integration tests for a monitor configured in a monotor yaml file.")
    parser.usage = "python test_monitor_handler_integration.py --monitor-config-path <path> --log-level <log level"
    parser.add_argument("--monitor-config-path", type=str, help="Path of monitor configuration file. Default is conf/monitor.yaml", default="tests/conf/monitor.yaml")
    parser.add_argument("--log-filename", type=str, help="Logfile name. Default is monitor_integration_test.log", default="monitor_integration_test.log")
    parser.add_argument("--log-level", type=str, help="Log level. Default is DEBUG", default="DEBUG")
    parser.add_argument("--test-delay", type=str, help="Delay in seconds after triggering a monitor event.", default=.5)
    args = parser.parse_args()

    # Setup logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG) # Set the overall minimum logging level
    # Remove default handlers if any (crucial for clean setup)
    for h in root_logger.handlers[:]:
        root_logger.removeHandler(h)

    console_handler_real = logging.StreamHandler()

    formatter = logging.Formatter(
        "%(asctime)s - %(levelname)s - %(name)s - %(message)s"
    )
    console_handler_real.setFormatter(formatter)
    root_logger.addHandler(console_handler_real)
    root_logger.debug("Root logger configured with console handler.")
    # --- End Central Logging Setup ---
 
    # Load configuration from the monitor config file
    with open(args.monitor_config_path, 'r') as file:
        monitor_config = yaml.safe_load(file)

    # monitor_config = ConfigHandler(args.monitor_config_path)
    log_config = monitor_config.get("logging")
    if log_config is None:
        print(f"Configuration for 'logging' not found in {args.monitor_config_path}.")
        sys.exit(1)

    LOG_FILE = log_config.get('log_filename', 'folder_monitor.log')
    LOG_FOLDER = log_config.get('log_folder', 'logs')
    MAX_BYTES = log_config.get('max_bytes', 10 * 1024 * 1024)  # Default to 10 MB
    BACKUP_COUNT = log_config.get('backup_count', 5)  # Default to

    # rotating_log_file = os.path.join(LOG_FOLDER, LOG_FILE)
    rotating_log_file = os.path.join(LOG_FOLDER, args.log_filename)
    # Ensure the log folder exists
    if not os.path.exists(LOG_FOLDER):
        try:
            os.makedirs(LOG_FOLDER)
            print(f"Log folder '{LOG_FOLDER}' created.")
        except OSError as e:
            print(f"Error creating log folder {LOG_FOLDER}: {e}")
            sys.exit(1)

    # These are the *actual* handlers that write to disk/console
    rotating_file_handler_real = logging.handlers.RotatingFileHandler(
        rotating_log_file,
        maxBytes=MAX_BYTES,
        backupCount=BACKUP_COUNT
    )

    formatter = logging.Formatter(
        "%(asctime)s - %(levelname)s - %(name)s - %(message)s"
    )
    rotating_file_handler_real.setFormatter(formatter)
    root_logger.addHandler(rotating_file_handler_real)
    logger = get_unique_logger(args.log_level)
    logger.debug("Processing monitors")
    monitors = monitor_config.get("monitors")

    # Iterate over monitors, creating a MonitorHandler for each one and starting it
    monitor_handlers = set()
    process_test_results : list[ProcessTestResult] = [] 
    for monitor in monitors:
        logger.debug(f"Generating events for monitor: [{monitor['name']}]")

        if not monitor.get("enabled"):
            logger.debug(f"Monitor {monitor['name']} is disabled. Skipping...")
            continue

        process_test_result = run_integration_check(monitor_name=monitor.get("name"), src_path=monitor.get("monitor_path"), destination_path=monitor.get("destination_path"), base_path=monitor.get("base_path"), logger=logger, test_delay=args.test_delay)
        process_test_results.append(process_test_result)

    # Print test resuls of all monitors
    total_success_count = 0
    total_failure_count = 0
    for process_test_result in process_test_results:
        (monitor_name, success_count, failure_count, test_results) = process_test_result.get_result()
        total_success_count += success_count
        total_failure_count += failure_count
        logger.info(f"===> BEGIN: test results for [{monitor_name}] <===")
        logger.info("==================================================")
        logger.info(f"Number of tests : {success_count + failure_count}")
        logger.info(f"Success count   : {success_count}")
        logger.info(f"Failure count   : {failure_count}")
        logger.info("==================================================")
        for result in test_results:
            logger.info(result)
        logger.info(f"===> END: test results for [{monitor_name}] <===")

    # Print totals over all monitors
    logger.info(f"===> Total counts for all monitors <===")
    logger.info("==================================================")
    total_tests = success_count + failure_count
    logger.info(f"Total number of tests : {total_success_count + total_failure_count}")
    logger.info(f"Total success count   : {total_success_count}")
    logger.info(f"Total failure count   : {total_failure_count}")
    logger.info("==== Test case output ===")

