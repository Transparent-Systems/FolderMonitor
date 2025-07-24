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
"""

import argparse
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
import utils

def get_destination_path(path, base_path, root_destination_path):
    path = path.replace("\\", "/")
    # Return part after base_path
    # Or entire path if base_path not found
    try:
        index = path.index(base_path)
        return_path = path[index + len(base_path):]
    except ValueError:
        return_path = path

    if return_path.startswith("/"):
        return f"{root_destination_path}{return_path}"
    else:
        return f"{root_destination_path}/{return_path}"

class ProcessTestResult():

    def __init__(self, monitor_name: str):
        self.monitor_name = monitor_name
        self.success_count = 0
        self.failure_count = 0
        self.test_results = []

    def process_result(self, test_name: str, ok: bool, result_output: str):
        # Declare which variables are global
        if ok:
            self.success_count += 1
            self.test_results.append(f"success  | {test_name}")
        else:
            self.failure_count += 1
            self.test_results.append(f"failure  | {test_name} | failure")
            self.test_results.append(f"         | {result_output}")

    def get_result(self):
        return (self.monitor_name, self.success_count, self.failure_count, self.test_results)


def run_integration_check(monitor_name: str, src_path = "data/Source",destination_path = "data/Destination", base_path = "", logger = None, delay_seconds=1):
    logger.debug("--- Rclone Integration Check ---")

    # Create rclone_handler to check files at destination_path
    rclone_handler = RcloneHandler(destination_path=destination_path, base_path=base_path, logger=logger, rclone_flags='')
    process_test_result = ProcessTestResult(monitor_name)

    try:
        test_name = "Test 1 : Create new file"
        logger.debug(f"\n3. Copying a test file to '{src_path}'...")
        file_name = "monitor_handler/Subfolder1/test1.txt"
        file_path = create_test_data(path=src_path, files=file_name)
        # Wait to let monitor finish
        time.sleep(delay_seconds)  # Sleep for a short duration to avoid busy-waiting
        dst_path = get_destination_path(path=file_path, base_path=base_path, root_destination_path=destination_path)
        rclone_command = ["lsf", "--format", "tshp", "--separator", " | ", dst_path] 
        (result_code, result_output) = rclone_handler.run_command(rclone_command)
        logger.debug(f"Check if file '{dst_path}' been created:\n{result_output}")
        process_test_result.process_result(test_name, result_code == 0, result_output)
    
        test_name = "Test 2 : Delete a file"
        file_name = "monitor_handler/Subfolder1/test1.txt"
        file_path = delete_test_data(path=src_path, files=file_name)
        logger.debug(f"\n3. Deleted source file : '{file_path}'")
        # Wait to let monitor finish deleting file
        time.sleep(delay_seconds)  # Sleep for a short duration to avoid busy-waiting
        dst_path = get_destination_path(path=file_path, base_path=base_path, root_destination_path=destination_path)
        logger.debug(f"Check if destination file exists: {dst_path}")
        rclone_command = ["lsf", "--format", "tshp", "--separator", " | ", dst_path] 
        (result_code, result_output) = rclone_handler.run_command(rclone_command)
        logger.debug(f"Check if file {dst_path} has been deleted:\n{result_output}")
        process_test_result.process_result(test_name, result_code !=0 , result_output)

        test_name = "Test 1 : Create subfolder with files. Check last file only"
        logger.debug(f"\n3. Creating files")
        file_name = "monitor_handler/Subfolder2/test1.txt"
        file_path = create_test_data(path=src_path, files=file_name)
        file_name = "monitor_handler/Subfolder2/test2.txt"
        file_path = create_test_data(path=src_path, files=file_name)
        # Wait to let monitor finish
        time.sleep(delay_seconds)  # Sleep for a short duration to avoid busy-waiting
        dst_path = get_destination_path(path=file_path, base_path=base_path, root_destination_path=destination_path)
        rclone_command = ["lsf", "--format", "tshp", "--separator", " | ", dst_path] 
        (result_code, result_output) = rclone_handler.run_command(rclone_command)
        logger.debug(f"Check if file '{dst_path}' been created:\n{result_output}")
        process_test_result.process_result(test_name, result_code == 0, result_output)

        # # Test 6: Emulate move file
        # logger.debug("Move file ...")
        # old_file_path = create_test_data(src_path, ["monitor_handler/Subfolder1/test3.txt"])
        # shutil.move(f"{src_path}/monitor_handler/Subfolder1/test3.txt", f"{src_path}/monitor_handler/Subfolder1/test3_moved.txt") 
        # # Delete old file at destination
        # (result_code, result_output) = handler.delete_file(old_file_path)
        # assert result_code == 0  

        # # Create new file at destination
        # (result_code, result_output) = handler.copy_file(f"{src_path}/monitor_handler/Subfolder1/test3_moved.txt")
        # logger.debug(f"Copy result code: {result_code}")
        # assert result_code == 0

        # # Test 7: Copy entire folder
        # logger.debug("Copy entire folder to destination ...")
        # test_files = []
        # test_files.append("monitor_handler/Subfolder3/test1.txt")
        # test_files.append("monitor_handler/Subfolder3/test2.txt")
        # file_path = create_test_data(src_path, test_files)
        # head = os.path.dirname(file_path)
        # (result_code, result_output) = handler.copy_folder(head)
        # logger.debug(f"Copy result code: {result_code}")
        # assert result_code == 0

        # # Check if subolder has been copied to destination
        # rclone_command = ["lsf", "--format", "tshp", "--separator", " | ", head] 
        # (result_code, result_output) = handler.run_command(rclone_command)
        # logger.debug(f"result_output:\n{result_output}")
        # file_name = os.path.basename(file_path)
        # assert file_name in result_output

        # # Test 8: Remove entire folder and contents from destination
        # logger.debug("Remove entire folder and contents from destination ...")
        # test_files = []
        # test_files.append("monitor_handler/Subfolder3/test1.txt")
        # test_files.append("monitor_handler/Subfolder3/test2.txt")
        # file_path = create_test_data(src_path, test_files)
        # head = os.path.dirname(file_path)
        # (result_code, result_output) = handler.delete_folder(head)
        # assert result_code == 0

        # # Check if subolder has been removed from destination
        # dst_path = get_destination_path(head, base_path, destination_path)
        # rclone_command = ["lsf", "--format", "tshp", "--separator", " | ", dst_path] 
        # (result_code, result_output) = handler.run_command(rclone_command)
        # assert result_code == 0
        # file_name = os.path.basename(file_path)
        # assert file_name not in result_output

        # Get test results
        (monitor_name, success_count, failure_count, test_results) = process_test_result.get_result()
        logger.info(f"=== Test results for monitor name [{monitor_name}] below. ===")
        logger.info("===========================")
        total_tests = success_count + failure_count
        logger.info(f"Total number of tests: {total_tests}")
        logger.info(f"Success count        : {success_count}")
        logger.info(f"Failure count        : {failure_count}")
        logger.info("===========================")
        for result in test_results:
            logger.info(result)
        logger.info("===========================")
    except Exception as e:
        logger.debug(f"\n--- Integration check for {monitor_name} FAILED: {e} ---")
    finally:
        logger.debug(f"\n--- Integration check cleanup")


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
        file_path = os.path.join(path, filename)
        head = os.path.dirname(file_path)
        try:
            os.makedirs(head, exist_ok=True)
        except OSError as e:
            logger.debug(f"Error creating folder {head}: {e}")
            sys.exit(1)

        with open(file_path, 'w') as f:
            logger.debug(f"Writing to file {filename}")
            f.write(f"Test data for {filename}\n")

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
        filename = filename.lstrip("/\\")
        file_path = os.path.join(path, filename)
        os.remove(file_path)
    
    return file_path

   
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="This script runs integration tests for a monitor configured in a monotor yaml file.")
    parser.usage = "python test_monitor_handler_integration.py --monitor-config-path <path> --log-level <log level"
    parser.add_argument("--monitor-config-path", type=str, help="Path of monitor configuration file. Default is conf/monitor.yaml", default="tests/conf/monitor.yaml")
    parser.add_argument("--logfile-name", type=str, help="Logfile name. Default is monitor_integration_test.log", default="monitor_integration_test.log")
    parser.add_argument("--log-level", type=str, help="Log level. Default is DEBUG", default="DEBUG")
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

    LOG_FILE = log_config.get('log_file_name', 'folder_monitor.log')
    LOG_FOLDER = log_config.get('log_folder', 'logs')
    MAX_BYTES = log_config.get('max_bytes', 10 * 1024 * 1024)  # Default to 10 MB
    BACKUP_COUNT = log_config.get('backup_count', 5)  # Default to

    # rotating_log_file = os.path.join(LOG_FOLDER, LOG_FILE)
    rotating_log_file = os.path.join(LOG_FOLDER, args.logfile_name)
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
    # logger = logging.getLogger()
    logger = utils.get_unique_logger(args.log_level)
    logger.debug("Processing monitors")
    monitors = monitor_config.get("monitors")

    # Iterate over monitors, creating a MonitorHandler for each one and starting it
    monitor_handlers = set()
    for monitor in monitors:
        logger.debug(f"Generating events for monitor: [{monitor['name']}]")

        if not monitor.get("enabled"):
            logger.debug(f"Monitor {monitor['name']} is disabled. Skipping...")
            continue

        run_integration_check(monitor_name=monitor.get("name"), src_path=monitor.get("monitor_path"), destination_path=monitor.get("destination_path"), base_path=monitor.get("base_path"), logger=logger)

    logger.info("Test for all monitors finished.")
