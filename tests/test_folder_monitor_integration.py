"""
Version: 1.0

This script makes changes to the monitor_path to trigger events in the MonitorHandler
The script depens on a folder_monitor running.
folder_monitor.py is started in another shell and runs as a seperate process

Pre-requisites:
Start folder_monitor using the same config.yaml file as this script
    From the application folder run:
    python.exe folder_monitor.py --config-path conf/config.tests.yaml

Important notes:
1)
This note relates to testing s3-compatible cloud storage.
S3 storage (or compatible versions like IDrive e2) is an object storage system. It does not have a real foldr structure.
Now, when in a tree with just 1 fie that file is deleted, the entire folder tree is gone.
For example: e2:mybucket/a/b/c/test1.txt
After deleting test1.txt, the only thing remaining is: e2:mybucket
2)
The behaviour for a file like "rclone ls <file>" is different between local storage and remote storage.
To get a more reliable check if a file exists on both local and remote storage we use "rclone lsjson <parent-folder>
3)
One or more integratin tests may fail if check_delay is not high enough for the monitor tested.
You can check this by looking at the console log where folder_monitor.py runs
If the console log stil shows log lines after this integration test has ended, than increase check-delay
"""

import argparse
import logging.handlers
import sys
import logging
import time
import yaml
import shutil
from pathlib import Path

# Add the scripts directory to the Python path
scriptspath = Path(__file__).parent / Path("../scripts")
sys.path.insert(0, scriptspath.resolve().as_posix())

from config_models import ConfigModels
from rclone_handler import RcloneHandler
from utils.testing_util import create_test_data, delete_test_data, create_big_file, ProcessTestResult
from utils.rclone_util import CheckPath
from utils.logging_util import get_unique_logger


"""
Pre-requisite: 
1) folder_monitor.py must be running with same config.yaml file as this script
2) Ensure that for testing purposes the test-delay in the config.yaml file is set to a value big enough to allow the monitor to process events
    This depends mainly on the cloud storage used and the performance of the system running folder_monitor.py

Description of test cases
Trigger events in monitor path src_path.
Then check if the expected result is found at destination path dst_path.
The rclone_handler is used to check files at the destination path.

All files and folder created will be in test subfolder
That way we can safely remove that test subfolder from source and destination
"""
def run_integration_check(
    monitor_name: str,
    source_path="data/Source",
    destination_path="data/Destination",
    logger=None,
    check_delay=1,
):

    logger.debug("--- FolderMonitor Integration Check ---")

    # Create rclone_handler to check files at destination_path
    rclone_handler = RcloneHandler(
        base_destination_path=destination_path,
        base_source_path=source_path,
        logger=logger,
        rclone_flags="",
    )

    process_test_result = ProcessTestResult(testsuite_name=monitor_name)
    check_path = CheckPath(rclone_handler=rclone_handler, check_delay=check_delay)
    logger.debug(
        f"Starting tests for monitor name [{monitor_name}] on monitor path [{source_path}]..."
    )

    try:
        #############################################
        test_name = "Test 0: Testing utils"
        #############################################
        logger.debug(f"==> {test_name}")
        file_name = "Subfolder1/test1.txt"
        # Create source file first, otherwise rclone_handler.copy_file may fail
        file_path = create_test_data(path=source_path, files=[file_name])
        (result_code, result_output) = rclone_handler.copy_file(source_path=file_path.as_posix())
        if result_code == 0:
            dst_path = rclone_handler.get_destination_path(path=file_path)
            (found, isdir, files) = check_path.path_exists(
                path=dst_path
            )

            process_test_result.process(
                test_name, (found and not isdir), files, f"verify this is a file: {dst_path}"
            )

            # Now check a file that does not exist
            dst_path = Path(source_path) / Path("file-does-not-exists.txt")
            (found, isdir, files) = check_path.path_exists(
                path=dst_path
            )
            process_test_result.process(
                test_name, (not found), files, f"verify file does not exist: {dst_path}"
            )

            # Now check Subfolder1 has been created at destination
            subfolder_path= Path(source_path) / Path("Subfolder1")
            dst_path = rclone_handler.get_destination_path(path=subfolder_path)
            (found, isdir, files) = check_path.path_exists(
                path=dst_path
            )
            process_test_result.process(
                test_name,
                (found and isdir),
                files,
                f"verify this is a directory: {dst_path}",
            )

            # Now check for a non-existent folder
            subfolder_path= Path(source_path) / Path("folder_does_not_exist")
            dst_path = rclone_handler.get_destination_path(path=subfolder_path)
            (found, isdir, files) = check_path.path_exists(
                path=dst_path
            )
            process_test_result.process(
                test_name, (not found), files, f"verify directory does not exist: {subfolder_path.name}"
            )
        else:
            process_test_result.process(
                test_name, (False), result_output, f"copy file {file_name}"
            )

        ##########################################################################
        test_name = "Test 1 : Create new file"
        ###########################################################################
        logger.debug(f"==> {test_name}")
        file_name = "test1.txt"
        file_path = create_test_data(path=source_path, files=[file_name])
        head = file_path.parent
        tail = file_path.name
        dst_path = rclone_handler.get_destination_path(path=head)
        (found, files) = check_path.file_exists(parent_path=dst_path, file_name=tail)
        process_test_result.process(test_name, (found), files)

        ###########################################################################
        test_name = "Test 2 : Delete a file"
        # Depends on: Test 1
        ###########################################################################
        logger.debug(f"==> {test_name}")
        file_name = "test1.txt"
        file_path = delete_test_data(path=source_path, files=[file_name])
        logger.debug(f"Deleted source file : '{file_path}'")
        head = file_path.parent
        tail = file_path.name
        dst_path = rclone_handler.get_destination_path(path=head)
        (found, files) = check_path.file_exists(parent_path=dst_path, file_name=tail)
        process_test_result.process(test_name, (not found), files)

        ###########################################################################
        test_name = "Test 3 : Create subfolder with files. Check last file only"
        ###########################################################################
        logger.debug(f"==> {test_name}")
        files = []
        files.append("Subfolder3/test1.txt")
        files.append("Subfolder3/test2.txt")
        files.append("Subfolder3/test3.txt")
        file_path = create_test_data(path=source_path, files=files)
        head = file_path.parent
        tail = file_path.name
        dst_path = rclone_handler.get_destination_path(path=head)
        (found, files) = check_path.file_exists(parent_path=dst_path, file_name=tail)
        process_test_result.process(test_name, (found), files)

        ##########################################################################
        test_name = "Test 4 : Delete subfolder."
        ###########################################################################
        logger.debug(f"==> {test_name}")
        files = []
        files.append("Subfolder4/test1")
        file_path_files = create_test_data(path=source_path, files=files)
        file_path = delete_test_data(path=source_path, files=["Subfolder4"])
        head = file_path.parent
        tail = file_path.name
        dst_path = rclone_handler.get_destination_path(path=head)
        # Check folder exists
        (found, files) = check_path.folder_exists(
            parent_path=dst_path, folder_name=tail
        )

        if found:
            # This can happen on local storage
            # Subfolder must be empty
            head = file_path_files.parent
            tail = file_path_files.name
            dst_path = rclone_handler.get_destination_path(path=head)
            (found, files) = check_path.file_exists(parent_path=head, file_name=tail)
            process_test_result.process(
                test_name, (not found), files, f"verify file does not exist: {tail}"
            )
        else:
            process_test_result.process(
                test_name, (not found), files, f"verify folder does not exist: {head}"
            )

        ###########################################################################
        test_name = "Test 5 : Rename file"
        ###########################################################################
        logger.debug(f"==> {test_name}")
        files = ["old_file.txt"]
        old_file_path = create_test_data(path=source_path, files=files)
        # Rename the file
        new_file_path = Path(source_path) / Path("new_file.txt")

        if new_file_path.exists():
            new_file_path.unlink()

        old_file_path.rename(new_file_path)
        # os.rename(src=old_file_path, dst=new_file_path)
        # Check if old file has been deleted from destination
        head = old_file_path.parent
        tail = old_file_path.name
        dst_path = rclone_handler.get_destination_path(path=head)
        (found, files) = check_path.file_exists(parent_path=dst_path, file_name=tail)
        process_test_result.process(
            test_name, (not found), files, f"check {tail} not found"
        )

        # Check if new file exists at destination
        head = new_file_path.parent
        tail = new_file_path.name
        dst_path = rclone_handler.get_destination_path(head)
        (found, files) = check_path.file_exists(parent_path=dst_path, file_name=tail)
        process_test_result.process(test_name, found, files, f"check {tail} found")

        ###########################################################################
        test_name = "Test 6 : Rename subfolder"
        ###########################################################################
        # Create Subfolder-old
        logger.debug(f"==> {test_name}")
        files = []
        files.append("Subfolder-old/test1.txt")
        files.append("Subfolder-old/test2.txt")
        file_path = create_test_data(path=source_path, files=files)

        # Remove Subfolder-new if it exists
        new_path = Path(source_path) / Path("Subfolder-new")
        if new_path.exists():
            shutil.rmtree(new_path)

        # Rename Subfolder-old to Subfolder-new
        head_old = file_path.parent
        head_new = head_old.replace(target=new_path.as_posix())

        # Check if Subfolder-old has been deleted from destination
        head = head_old.parent
        tail = head_old.name
        dst_path = rclone_handler.get_destination_path(head)
        (found, files) = check_path.folder_exists(
            parent_path=dst_path, folder_name=tail
        )
        process_test_result.process(
            test_name, (not found), files, f"check {tail} not found"
        )

        # Check if new folder exists at destination
        head = head_new.parent
        tail = head_new.name
        dst_path = rclone_handler.get_destination_path(head)
        (found, files) = check_path.folder_exists(
            parent_path=dst_path, folder_name=tail
        )
        process_test_result.process(test_name, found, files, f"check {tail} found")

        #############################################
        test_name = "Test 7: Write big file"
        #############################################
        logger.debug(f"==> {test_name}")
        file_name = "big-test-file.txt"

        # Delete big file first as a pre-condition
        file_path = delete_test_data(path=source_path, files=[file_name])
        logger.debug(f"Deleted source file : '{file_path}'")

        # Check file exists at destination path
        dst_path = rclone_handler.get_destination_path(path=file_path)
        (found, isdir, files) = check_path.path_exists(
            path=dst_path
        )

        process_test_result.process(
            test_name, (not found), files, f"Verify that file does not exist at destination: {dst_path}"
        )

        # Now create the same big file
        file_path = create_big_file(
            path=source_path, filename=file_name, write_duration_seconds=15
        )

        # Check file has been created at destination path
        # Wait for another 10 seconds before checking as this is a big file
        wait_seconds = 10
        logger.debug(f"Waiting for another {wait_seconds} seconds before checking...")
        time.sleep(wait_seconds)
        dst_path = rclone_handler.get_destination_path(path=file_path)
        (found, isdir, files) = check_path.path_exists(
            path=dst_path
        )

        process_test_result.process(
            test_name, (found), files, f"Verify file exists at destination: {dst_path}"
        )
        #############################################

        #############################################
        test_name = "Test 8: Write many files"
        # The purpose of this test is to check if no files are skipped by the monitor when files are created rapidly
        #############################################
        logger.debug(f"==> {test_name}")

        file_paths = []
        max_file_count = 6
        for i in range(1, max_file_count):
            file_name = f"many_files_{i}.txt"
            # Delete files first
            file_path = delete_test_data(path=source_path, files=[file_name])
            logger.debug(f"Deleted source file : '{file_path}'")
            file_paths.append(file_path)

        # Now check files do not exist (anymore) at destiation
        for file_path in file_paths:
            # Check file exists at destination path
            dst_path = rclone_handler.get_destination_path(path=file_path)
            (found, isdir, files) = check_path.path_exists(
                path=file_path
            )

            process_test_result.process(
                test_name, (not found), files, f"Verify that file does not exist at destination: {dst_path}"
            )

        # Now create many files at once before checking
        file_paths = []
        for i in range(1, max_file_count):
            file_name = f"many_files_{i}.txt"
            file_path = create_test_data(path=source_path, files=[file_name])
            file_paths.append(file_path)

        # Check files have been created at destination path
        for file_path in file_paths:
            dst_path = rclone_handler.get_destination_path(path=file_path)
            (found, isdir, files) = check_path.path_exists(
                path=dst_path
            )

            process_test_result.process(
                test_name, (found), files, f"Verify file exists at destination: {dst_path}"
            )
        #############################################

    except Exception as e:
        logger.debug(f"\n--- Integration check for {monitor_name} FAILED: {e} ---")
        process_test_result.process(
            test_name, False, f"Fatal error executing tests: {e}"
        )
    finally:
        logger.debug(f"\n--- Integration check cleanup for {monitor_name}")

    return process_test_result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="This script runs integration tests for a monitor configured in a config.yaml file."
    )
    parser.usage = "python test_folder_monitor_integration.py --config-path <path> --log-level <log level"
    parser.add_argument(
        "--config-path",
        type=str,
        help="Path of monitor configuration file. Default is conf/config.yaml",
        default="conf/config.tests.yaml",
    )
    parser.add_argument(
        "--log-file_name",
        type=str,
        help="Logfile name. Default is monitor_integration_test.log",
        default="monitor_integration_test.log",
    )
    parser.add_argument(
        "--log-level", type=str, help="Log level. Default is DEBUG", default="DEBUG"
    )
    parser.add_argument(
        "--check-delay",
        type=str,
        help="Delay in seconds after triggering a monitor event.",
        default=1,
    )
    args = parser.parse_args()

    # Setup logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)  # Set the overall minimum logging level
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

    # First validate monitor config file
    if not ConfigModels().validate(config_path=args.config_path, logger=root_logger):
        root_logger.error(
            f"Configuration file '{args.config_path}' is invalid. Exiting."
        )
        sys.exit(1)

    root_logger.debug(f"Configuration file '{args.config_path}' is valid.")

    # Load configuration from the monitor config file
    with open(args.config_path, "r") as file:
        monitor_config = yaml.safe_load(file)

    # monitor_config = ConfigHandler(args.config_path)
    log_config = monitor_config.get("logging")
    if log_config is None:
        print(f"Configuration for 'logging' not found in {args.config_path}.")
        sys.exit(1)

    LOG_FILE = log_config.get("log_file_name", "folder_monitor.log")
    LOG_FOLDER = log_config.get("log_folder", "logs")
    MAX_BYTES = log_config.get("max_bytes", 10 * 1024 * 1024)  # Default to 10 MB
    BACKUP_COUNT = log_config.get("backup_count", 5)  # Default to

    # Create log folder if it does not exist
    log_folder_path = Path(LOG_FOLDER)
    try:
        if not log_folder_path.exists():
            log_folder_path.mkdir(parents=True)
            print(f"Log folder '{LOG_FOLDER}' created.")
    except OSError as e:
        print(f"Error creating log folder {LOG_FOLDER}: {e}")
        sys.exit(1)

    # These are the *actual* handlers that write to disk/console
    rotating_log_file = Path(LOG_FOLDER) / Path(args.log_file_name)
    rotating_file_handler_real = logging.handlers.RotatingFileHandler(
        rotating_log_file.as_posix(), maxBytes=MAX_BYTES, backupCount=BACKUP_COUNT
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
    process_test_results: list[ProcessTestResult] = []
    check_delay_default = args.check_delay
    for monitor in monitors:
        logger.debug(f"Generating events for monitor: [{monitor['name']}]")

        if not monitor.get("enabled"):
            logger.debug(f"Monitor {monitor['name']} is disabled. Skipping...")
            continue

        # Create monitor_path if not exists
        monitor_path = Path(monitor.get("monitor_path"))
        if not monitor_path.exists():
            monitor_path.mkdir(parents=True)
            logger.debug(f"Created monitor_path: {monitor_path}")

        monitor_name = monitor.get("name")
        destination_path = monitor.get("destination_path")
        testing_config = monitor.get("testing")
        check_delay = testing_config.get("check_delay", args.check_delay)
        process_test_result = run_integration_check(
            monitor_name=monitor_name,
            source_path=monitor_path,
            destination_path=destination_path,
            logger=logger,
            check_delay=check_delay,
        )
        process_test_results.append(process_test_result)

    # Print test resuls of all monitors
    total_success_count = 0
    total_failure_count = 0
    total_duration = 0
    for process_test_result in process_test_results:
        total_success_count += process_test_result.success_count
        total_failure_count += process_test_result.failure_count
        total_duration += process_test_result.duration
        logger.info(
            f"===> BEGIN: test results for [{process_test_result.testsuite_name}] <==="
        )
        logger.info("==================================================")
        logger.info(
            f"Number of tests : {process_test_result.success_count + process_test_result.failure_count}"
        )
        logger.info(f"Success count   : {process_test_result.success_count}")
        logger.info(f"Failure count   : {process_test_result.failure_count}")
        logger.info(f"Duration        : {process_test_result.duration: .2f} seconds")
        logger.info("==================================================")

        len_test_results = len(process_test_result.test_results)
        max_width = len(str(len_test_results))
        for test_result in process_test_result.test_results:
            test_case_name = test_result.get("test_case_name")
            test_step_name = test_result.get("test_step_name")
            test_duration = test_result.get("test_duration")
            test_counter = test_result.get("test_counter")

            if len(test_step_name) == 0:
                test_full_name = test_case_name
            else:
                test_full_name = f"{test_case_name} - {test_step_name}"

            if test_result.get("test_ok"):
                logger.info(
                    f"success    | {test_counter:>{max_width}} : {test_full_name}"
                )
                logger.info(f"           |      ==> duration: {test_duration: .2f} s")
            else:
                logger.info(
                    f"failure    | {test_counter:>{max_width}} : {test_full_name}"
                )
                logger.info(f"           |      ==> duration: {test_duration: .2f} s")

                for item in test_result.get("test_output"):
                    logger.info(f"           |      {item}")

        logger.info(
            f"===> END: test results for [{process_test_result.testsuite_name}] <==="
        )

    # Print totals over all monitors
    logger.info(f"===> Total counts for all monitors <===")
    logger.info("==================================================")
    logger.info(f"Total number of tests : {total_success_count + total_failure_count}")
    logger.info(f"Total success count   : {total_success_count}")
    logger.info(f"Total failure count   : {total_failure_count}")
    logger.info(f"Total duration        : {total_duration: .2f} seconds")
    logger.info(f"===> End total counts for all monitors <===")
