import argparse
import json
import os
import sys
import logging
import shutil
import yaml
from logging.handlers import RotatingFileHandler

# Add the scripts directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../scripts')))

from utils import create_test_data, delete_test_data, get_unique_logger, ProcessTestResult, check_basename_in_path 
from rclone_handler import RcloneHandler


def run_integration_check(testsuite_name: str, source_path: str, destination_path: str, rclone_flags: str, logger: logging.Logger) -> ProcessTestResult:
    logger.debug("--- Rclone Integration Check ---")
    process_test_result = ProcessTestResult(testsuite_name=testsuite_name)
    rclone_handler = RcloneHandler(
        base_destination_path=destination_path, 
        base_source_path=source_path, 
        logger=logger, 
        rclone_flags=rclone_flags
        )

    try:
        testname = "Test 1: Get Version"
        logger.debug(testname)
        (result_code, result_output) = rclone_handler.get_rclone_version()
        result_output = result_output.replace("\n", " ; ")
        process_test_result.process_result(testname, ("rclone" in result_output.lower()), result_output)

        testname = "Test 2: List Remotes"
        logger.debug(testname)
        (result_code, result_output) = rclone_handler.list_remotes()
        result_output = result_output.replace("\n", " ; ")
        process_test_result.process_result(testname, (result_code == 0), result_output)

        testname = "Test 3: Copy a test file to remote"
        logger.debug(testname)
        # Create file first 
        file_path = f"{source_path}/test1.txt"
        file_path = create_test_data(path=source_path, files="test1.txt")
        (result_code, result_output) = rclone_handler.copy_file(file_path)
        process_test_result.process_result(testname, (result_code == 0), result_output)

        testname = "Test 4: Copy file to remote"
        logger.debug(testname)
        filename = "test1.txt"
        file_path = create_test_data(path=source_path, files=filename)
        # Create source file first, otherwise rclone_handler.copy_file may fail
        (result_code, result_output) = rclone_handler.copy_file(file_path)
        if result_code !=0:
            process_test_result.process_result(testname, (False), result_output, f"copy file {filename}")
        else:
            dst_path = rclone_handler.get_destination_path(path=file_path)
            parent_folder = os.path.dirname(dst_path)
            (found, files) = check_basename_in_path(
                rclone_handler=rclone_handler, 
                remote_path=parent_folder,
                basename=filename
                )
            
            process_test_result.process_result(testname, (found), files, f"verify file {filename} on remote")

        #===
        testname = "Test 5: Delete a file at remote"
        logger.debug(testname)
        filename = "test2.txt"

        # Create source file first, otherwise rclone_handler.copy_file may fail;
        file_path = create_test_data(path=source_path, files=filename)

        # Now copy file to destination
        (result_code, result_output) = rclone_handler.copy_file(file_path)
        if result_code !=0:
            process_test_result.process_result(testname, (False), result_output, f"copy file {filename} to remote")
        else:
            # Now delete the destination file
            dst_path = rclone_handler.get_destination_path(path=file_path)
            (result_code, result_output) = rclone_handler.delete_file(dst_path)

            # Check if the destination file has indeed been deleted
            parent_folder = os.path.dirname(dst_path)
            (found, files) = check_basename_in_path(
                rclone_handler=rclone_handler, 
                remote_path=parent_folder,
                basename=filename
                )

            # File should not be found
            process_test_result.process_result(testname, (not found), files, f"check file {filename} deleted")

        #===
        testname = "Test 6: Create folder with files"
        logger.debug(testname)
        test_files = []
        test_files.append("Subfolder1/test1.txt")
        test_files.append("Subfolder1/test2.txt")
        test_files.append("Subfolder1/test3.txt")

        # Create folder on source first
        file_path = create_test_data(source_path, test_files)

        # Now copy folder to destination
        head = os.path.dirname(file_path)
        (result_code, result_output) = rclone_handler.copy_folder(head)
        process_test_result.process_result(testname, (result_code == 0), result_output, f"copy folder {os.path.basename(head)}")

        # Check if subfolder has been copied to destination
        # There should be at least 3 files in the subfolder now
        destination_path = rclone_handler.get_destination_path(head)
        filename = os.path.basename(file_path)
        (found, files) = check_basename_in_path(
            rclone_handler=rclone_handler, 
            remote_path=destination_path,
            basename=filename
            )

        # We should have found filename and there should be at least len(test_files) files
        result = (found and len(files) >= len(test_files))
        process_test_result.process_result(testname, (result), files, f"found file {filename} on remote")

        #====
        testname = "Test 7: Remove folder from remote"
        logger.debug(testname)
        test_files = []
        test_files.append("Subfolder2/test1.txt")
        test_files.append("Subfolder2/test2.txt")
        test_files.append("Subfolder2/test3.txt")

        # Create folder on source first
        file_path = create_test_data(source_path, test_files)

        # Now copy folder to destination
        head = os.path.dirname(file_path)
        (result_code, result_output) = rclone_handler.copy_folder(head)
        process_test_result.process_result(testname, (result_code == 0), result_output, f"copy folder {os.path.basename(head)} to remote")

        # Check if subfolder has been copied to destination
        # There should be at least 3 files in the subfolder now
        destination_path = rclone_handler.get_destination_path(head)
        filename = os.path.basename(file_path)
        (found, files) = check_basename_in_path(
            rclone_handler=rclone_handler, 
            remote_path=destination_path,
            basename=filename
            )

        # We should have found filename and there should be at least test_file.len files
        result = (found and len(files) >= len(test_files))
        process_test_result.process_result(testname, (result), files, f"check folder {filename} exists")

        # Now delete the destination folder
        head = os.path.dirname(file_path)
        destination_path = rclone_handler.get_destination_path(head)
        (result_code, result_output) = rclone_handler.delete_folder(destination_path)
        process_test_result.process_result(testname, (result_code == 0), result_output, f"delete folder {os.path.basename(head)}")

        # Check if folder has been deleted at destination
        # Get parent of subfolder, then check if folder exists
        parent_folder = os.path.dirname(head)
        destination_path = rclone_handler.get_destination_path(parent_folder)
        (found, files) = check_basename_in_path(
            rclone_handler=rclone_handler, 
            remote_path=destination_path,
            basename=head
            )
        
        process_test_result.process_result(testname, (not found), result_output, f"check folder {os.path.basename(head)} deleted")
 

        logger.debug("\n--- All integration checks done ---")

    except Exception as e:
        logger.debug(f"\n--- Integration check FAILED: {e} ---")
    finally:
        logger.debug(f"\n--- Integration check cleanup")

    return process_test_result
  
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="This script runs integration tests for rclone_handler. The configuration is in a monitor yaml file.")
    parser.usage = "python test_rclone_handler_integration.py --monitor-config-path <path> --log-level <log level"
    parser.add_argument("--monitor-config-path", type=str, help="Path of monitor configuration file. Default is test/conf/monitor.yaml", default="tests/conf/monitor.yaml")
    parser.add_argument("--log-filename", type=str, help="Logfile name. Default is test_rclone_handler_integration.log", default="test_rclone_handler_integration.log")
    parser.add_argument("--log-level", type=str, help="Log level. Default is DEBUG", default="DEBUG")
    parser.add_argument("--test-delay", type=str, help="Delay in seconds.", default=.5)
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

    # LOG_FILE = log_config.get('log_filename', 'test_rclone_handler_integration.log')
    LOG_FOLDER = log_config.get('log_folder', 'logs')
    MAX_BYTES = log_config.get('max_bytes', 10 * 1024 * 1024)  # Default to 10 MB
    BACKUP_COUNT = log_config.get('backup_count', 5)  # Default to

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
    logger.debug("Before calling run_integration_check")

    monitors = monitor_config.get("monitors")
    process_test_results: list[ProcessTestResult] = []
    for monitor in monitors:
        monitor_name = monitor.get("name") 
        subfolder = "test_rclone_handler_integration"
        source_path = monitor.get("monitor_path")
        source_path = source_path.rstrip("/\\")
        source_path = f"{source_path}/{subfolder}"
        destination_path = monitor.get("destination_path")
        destination_path = destination_path.rstrip("/\\")
        destination_path = f"{destination_path}/{subfolder}"
 
        process_test_result = run_integration_check(
            testsuite_name=monitor_name,
            source_path=source_path,
            destination_path=destination_path,
            rclone_flags=monitor.get("rclone_flags", ""),
            logger=logger
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
