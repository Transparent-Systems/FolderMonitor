"""
This script makes changes to the monitor_path to trigger events in the MonitorHandler
The script depens on a folder_monitor running.
folder_monitor runs in a separate script
When folder_monitor would be started in this script there could be thread racing conditions that would affect the test results
In addition: we want to test a running file_monitor not monitor_handler
Pre-requisites:
Start folder_monitor using the same monitor yaml file as this script
    From the application folder run:
    python.exe ./scripts/folder_monitor.py --monitor-config-path tests/conf/monitor.yaml

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
from utils import create_test_data, delete_test_data, get_unique_logger, check_basename_in_path, ProcessTestResult


def run_integration_check(monitor_name: str, source_path = "data/Source",destination_path = "data/Destination", logger = None, test_delay=1):
    """
    Trigger events in monitor path src_path
    All files and folder created will be in test subfolder
    That way we can safely remove that test subfolder from source and destination
    """
    logger.debug("--- Rclone Integration Check ---")
    test_src_path = os.path.join(source_path, "test_folder_monitor_integration")

    # Create rclone_handler to check files at destination_path
    rclone_handler = RcloneHandler(base_destination_path=destination_path, base_source_path=source_path, logger=logger, rclone_flags='')
    process_test_result = ProcessTestResult(monitor_name)
    logger.debug(f"Starting tests for monitor name [{monitor_name}] on monitor path [{source_path}]...")

    try:
        testname = "Test 1 : Create new file"
        filename = "test1.txt"
        filepath = create_test_data(path=test_src_path, files=filename)
        time.sleep(test_delay)  # Sleep for a short duration
        parent_folder = os.path.dirname(filepath)
        dst_path = rclone_handler.get_destination_path(path=parent_folder)
        basename = os.path.basename(filepath)
        (found, files) = check_basename_in_path(rclone_handler, remote_path=dst_path, basename=basename)
        process_test_result.process_result(testname, (found), files)
    
        # testname = "Test 2 : Delete a file"
        # filename = "test1.txt"
        # filepath = delete_test_data(path=test_src_path, files=filename)
        # logger.debug(f"Deleted source file : '{filepath}'")
        # time.sleep(test_delay)  # Sleep for a short duration
        # # Get destination path of parent folder
        # parent_folder = os.path.dirname(filepath)
        # dst_path = rclone_handler.get_destination_path(path=parent_folder)
        # basename = os.path.basename(filepath)
        # (found, files) = check_basename_in_path(rclone_handler, remote_path=dst_path, filename=basename)
        # process_test_result.process_result(testname, (not found), files)

        # testname = "Test 3 : Create subfolder with files. Check last file only"
        # files = []
        # files.append("Subfolder1/test1.txt")
        # files.append("Subfolder1/test2.txt")
        # files.append("Subfolder1/test3.txt")
        # filepath = create_test_data(path=test_src_path, files=files)
        # # Wait to let monitor finish
        # time.sleep(test_delay)  # Sleep for a short duration
        # parent_folder = os.path.dirname(filepath)
        # dst_path = rclone_handler.get_destination_path(path=parent_folder)
        # basename = os.path.basename(filepath)
        # (found, files) = check_basename_in_path(rclone_handler, remote_path=dst_path, filename=basename)
        # process_test_result.process_result(testname, (found and len(files) == 3), files)

        # testname = "Test 4 : Delete subfolder."
        # files = []
        # files.append("Subfolder1")
        # filepath = delete_test_data(path=test_src_path, files=files)
        # # Wait to let monitor finish
        # time.sleep(test_delay)  # Sleep for a short duration
        # parent_folder = os.path.dirname(filepath)
        # dst_path = rclone_handler.get_destination_path(path=parent_folder)
        # basename = os.path.basename(filepath)
        # (found, files) = check_basename_in_path(rclone_handler, remote_path=dst_path, filename=basename)
        # process_test_result.process_result(testname, (not found), files)


        # testname = "Test 5 : Rename file"
        # files ="old_file.txt"
        # old_file_path = create_test_data(path=test_src_path, files=files)
        # time.sleep(test_delay)  # Sleep for a short duration
        # # Rename the file
        # new_file_path = os.path.join(test_src_path, "new_file.txt")

        # if (os.path.exists(new_file_path)):
        #     os.remove(new_file_path)

        # os.rename(src=old_file_path, dst=new_file_path)
        # time.sleep(test_delay)  # Sleep for a short duration
        # parent_folder = test_src_path
        # dst_path = rclone_handler.get_destination_path(path=parent_folder)
        # # Check if old file has been deleted from destination
        # basename = os.path.basename(old_file_path)
        # (found, files) = check_basename_in_path(rclone_handler, remote_path=dst_path, filename=basename)
        # process_test_result.process_result(f"{testname}-1", (not found), files)
        # # Check if new file exists at destination
        # basename = os.path.basename(new_file_path)
        # (found, files) = check_basename_in_path(rclone_handler, remote_path=dst_path, filename=basename)
        # process_test_result.process_result(f"{testname}-2", found, files)


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

        monitor_name = monitor.get("name")
        monitor_path = monitor.get("monitor_path")
        destination_path = monitor.get("destination_path")
        process_test_result = run_integration_check(
            monitor_name=monitor_name,
            source_path=monitor_path,
            destination_path=destination_path,
            logger=logger, 
            test_delay=args.test_delay
            )
        process_test_results.append(process_test_result)

    # Print test resuls of all monitors
    total_success_count = 0
    total_failure_count = 0
    total_duration = 0
    for process_test_result in process_test_results:
        # (testsuite_name, success_count, failure_count, test_results, duration) = process_test_result.get_result()
        total_success_count += process_test_result.success_count
        total_failure_count += process_test_result.failure_count
        total_duration += process_test_result.duration
        logger.info(f"===> BEGIN: test results for [{process_test_result.testsuite_name}] <===")
        logger.info("==================================================")
        logger.info(f"Number of tests : {process_test_result.success_count + process_test_result.failure_count}")
        logger.info(f"Success count   : {process_test_result.success_count}")
        logger.info(f"Failure count   : {process_test_result.failure_count}")
        logger.info(f"Duration        : {process_test_result.duration: .2f} seconds")
        logger.info("==================================================")
        for result in process_test_result.test_results:
            logger.info(result)
        logger.info(f"===> END: test results for [{process_test_result.testsuite_name}] <===")

    # Print totals over all monitors
    logger.info(f"===> Total counts for all monitors <===")
    logger.info("==================================================")
    logger.info(f"Total number of tests : {total_success_count + total_failure_count}")
    logger.info(f"Total success count   : {total_success_count}")
    logger.info(f"Total failure count   : {total_failure_count}")
    logger.info(f"Total duration        : {total_duration: .2f} seconds")
    logger.info(f"===> End total counts for all monitors <===")

