"""
Version: 1.0

Test integration script for rclone handler.
The scipt iterates over monitors configured in a yaml file.
The same test suite is used for each monitor.
Test metrics and results are printed after processing all monitors
This sucess and failure rate is show and the duration of each test for an individual monitor and summarized over all monitors.
"""

import argparse
import sys
import logging
import yaml
from logging.handlers import RotatingFileHandler
from pathlib import Path

# Add the scripts directory to the Python path
scriptspath = Path(__file__).parent / Path("../scripts")
sys.path.insert(0, scriptspath.resolve().as_posix())

from rclone_handler import RcloneHandler
from utils.testing_util import create_test_data, ProcessTestResult
from utils.rclone_util import CheckPath
from utils.logging_util import get_unique_logger


def run_integration_check(
    testsuite_name: str,
    source_path: str,
    destination_path: str,
    rclone_flags: str,
    logger: logging.Logger,
) -> ProcessTestResult:
    logger.debug("--- Rclone Integration Check ---")
    process_test_result = ProcessTestResult(testsuite_name=testsuite_name)
    rclone_handler = RcloneHandler(
        base_destination_path=destination_path,
        base_source_path=source_path,
        logger=logger,
        rclone_flags=rclone_flags,
    )
    check_path = CheckPath(rclone_handler=rclone_handler, check_delay=0)

    try:
        #############################################
        testname = "Test 0: Testing utils"
        logger.debug(f"==> {testsuite_name} -> {testname}")
        file_name = "Subfolder1/test1.txt"
        # Create source file first, otherwise rclone_handler.copy_file may fail
        file_path = create_test_data(path=source_path, files=[file_name])
        (result_code, result_output) = rclone_handler.copy_file(file_path.as_posix())
        if result_code == 0:
            head = file_path.parent
            tail = file_path.name
            dst_path = rclone_handler.get_destination_path(path=head)
            (found, isdir, files) = check_path.basename_exists(
                base_name=tail, parent_path=dst_path
            )

            # Check this is a file
            process_test_result.process(
                testname, (found and not isdir), files, f"verify this is a file: {tail}"
            )

            # Now check a file that does not exist
            tail = "file-does-not-exists.txt"
            (found, isdir, files) = check_path.basename_exists(
                base_name=tail, parent_path=dst_path
            )
            process_test_result.process(
                testname, (not found), files, f"verify file does not exist: {tail}"
            )

            # Now check Subfolder1 has been created at destination
            head2 = head.parent
            tail2 = head.name
            dst_path = rclone_handler.get_destination_path(path=head2)
            (found, isdir, files) = check_path.basename_exists(
                base_name=tail2, parent_path=dst_path
            )
            process_test_result.process(
                testname,
                (found and isdir),
                files,
                f"verify this is a directory: {tail2}",
            )

            # Now check for a non-existent folder
            tail = "folder_does_not_exist"
            (found, isdir, files) = check_path.basename_exists(
                base_name=tail, parent_path=dst_path
            )
            process_test_result.process(
                testname, (not found), files, f"verify directory does not exist: {tail}"
            )
        else:
            process_test_result.process(
                testname, (False), result_output, f"copy file {file_name}"
            )

        #############################################
        testname = "Test 1: Get Version"
        logger.debug(f"==> {testsuite_name} -> {testname}")
        (result_code, result_output) = rclone_handler.get_rclone_version()
        result_output = result_output.replace("\n", " ; ")
        process_test_result.process(
            testname, ("rclone" in result_output.lower()), result_output
        )

        #############################################
        testname = "Test 2: List Remotes"
        logger.debug(f"==> {testsuite_name} -> {testname}")
        (result_code, result_output) = rclone_handler.list_remotes()
        result_output = result_output.replace("\n", " ; ")
        process_test_result.process(testname, (result_code == 0), result_output)

        #############################################
        testname = "Test 3: Copy file to remote"
        logger.debug(f"==> {testsuite_name} -> {testname}")
        file_name = "test1.txt"
        file_path = create_test_data(path=source_path, files=[file_name])
        # Create source file first, otherwise rclone_handler.copy_file may fail
        (result_code, result_output) = rclone_handler.copy_file(file_path.as_posix())
        if result_code == 0:
            head = file_path.parent
            tail = file_path.name
            dst_path = rclone_handler.get_destination_path(path=head)
            (found, files) = check_path.file_exists(
                parent_path=dst_path, file_name=tail
            )

            process_test_result.process(
                testname, (found), files, f"verify file {tail} on remote"
            )
        else:
            process_test_result.process(
                testname, (False), result_output, f"copy file {file_name}"
            )

        #############################################
        testname = "Test 4: Delete a file at remote"
        logger.debug(f"==> {testsuite_name} -> {testname}")
        file_name = "test2.txt"

        # Create source file first, otherwise rclone_handler.copy_file may fail;
        file_path = create_test_data(path=source_path, files=[file_name])

        # Now copy file to destination
        (result_code, result_output) = rclone_handler.copy_file(file_path.as_posix())
        if result_code != 0:
            process_test_result.process(
                testname, (False), result_output, f"copy file {file_name} to remote"
            )
        else:
            # Now delete the destination file
            dst_path = rclone_handler.get_destination_path(path=file_path)
            (result_code, result_output) = rclone_handler.delete_file(dst_path)

            # Check if the destination file has indeed been deleted
            parent_folder = Path(dst_path).parent
            file_name = Path(dst_path).name
            (found, files) = check_path.file_exists(
                parent_path=parent_folder, file_name=file_name
            )

            # File should not be found
            process_test_result.process(
                testname, (not found), files, f"check file {file_name} deleted"
            )

        #############################################
        testname = "Test 5: Create folder with files"
        logger.debug(f"==> {testsuite_name} -> {testname}")
        files = []
        files.append("Subfolder1/test1.txt")
        files.append("Subfolder1/test2.txt")
        files.append("Subfolder1/test3.txt")

        # Create files on source_path first
        file_path = create_test_data(path=source_path, files=files)

        # Now copy folder to destination
        head = file_path.parent
        (result_code, result_output) = rclone_handler.copy_folder(head)
        process_test_result.process(
            testname,
            (result_code == 0),
            result_output,
            f"copy folder {head.name}",
        )

        # Check if subfolder has been copied to destination
        # There should be at least 3 files in the subfolder now
        destination_path = rclone_handler.get_destination_path(head.as_posix())
        file_name = file_path.name
        (found, files) = check_path.file_exists(
            parent_path=destination_path, file_name=file_name
        )

        # We should have found file_name and there should be at least len(files) files
        result = found and len(files) >= len(files)
        process_test_result.process(
            testname, (result), files, f"found file {file_name} on remote"
        )

        #############################################
        testname = "Test 6: Remove folder from remote"
        logger.debug(f"==> {testsuite_name} -> {testname}")
        files = []
        files.append("Subfolder2/test1.txt")
        files.append("Subfolder2/test2.txt")
        files.append("Subfolder2/test3.txt")

        # Create folder and files on source first
        file_path = create_test_data(path=source_path, files=files)

        # Now copy folder to destination
        head = file_path.parent
        (result_code, result_output) = rclone_handler.copy_folder(head)
        process_test_result.process(
            testname,
            (result_code == 0),
            result_output,
            f"copy folder {head.name} to remote",
        )

        # Check if subfolder has been copied to destination
        # There should be at least 3 files in the subfolder now
        destination_path = rclone_handler.get_destination_path(head)
        file_name = file_path.name
        (found, files) = check_path.file_exists(
            parent_path=destination_path, file_name=file_name
        )

        # We should have found file_name and there should be at least test_file.len files
        result = found and len(files) >= len(files)
        process_test_result.process(
            testname, (result), files, f"check folder {file_name} exists"
        )

        # Now delete the destination folder
        head = file_path.parent
        tail = file_path.name
        destination_path = rclone_handler.get_destination_path(head)
        # Method purge_folder will also delte the top-level folder.
        (result_code, result_output) = rclone_handler.purge_folder(destination_path)
        process_test_result.process(
            testname,
            (result_code == 0),
            result_output,
            f"delete folder {head.name}",
        )

        # Check if folder has been deleted at destination
        # Get parent of subfolder, then check if folder exists
        head = file_path.parent
        tail = file_path.name
        destination_path = rclone_handler.get_destination_path(head)
        (found, files) = check_path.folder_exists(
            parent_path=destination_path, folder_name=tail
        )

        process_test_result.process(
            testname,
            (not found),
            result_output,
            f"check folder {head.name} deleted",
        )
        logger.debug("\n--- All integration checks done ---")

    except Exception as e:
        logger.debug(f"\n--- Integration check FAILED: {e} ---")
    finally:
        logger.debug(f"\n--- Integration check cleanup")

    return process_test_result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="This script runs integration tests for rclone_handler. The configuration is in a monitor yaml file."
    )
    parser.usage = "python test_rclone_handler_integration.py --config-path <path> --log-level <log level"
    parser.add_argument(
        "--config-path",
        type=str,
        help="Path of monitor configuration file. Default is test/conf/config.yaml",
        default="tests/conf/config.yaml",
    )
    parser.add_argument(
        "--log-filename",
        type=str,
        help="Logfile name. Default is test_rclone_handler_integration.log",
        default="test_rclone_handler_integration.log",
    )
    parser.add_argument(
        "--log-level", type=str, help="Log level. Default is DEBUG", default="DEBUG"
    )
    parser.add_argument("--test-delay", type=str, help="Delay in seconds.", default=0.5)
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

    # Load configuration from the monitor config file
    with open(args.monitor_config_path, "r") as file:
        monitor_config = yaml.safe_load(file)

    # monitor_config = ConfigHandler(args.monitor_config_path)
    log_config = monitor_config.get("logging")
    if log_config is None:
        print(f"Configuration for 'logging' not found in {args.monitor_config_path}.")
        sys.exit(1)

    # LOG_FILE = log_config.get('log_filename', 'test_rclone_handler_integration.log')
    LOG_FOLDER = log_config.get("log_folder", "logs")
    MAX_BYTES = log_config.get("max_bytes", 10 * 1024 * 1024)  # Default to 10 MB
    BACKUP_COUNT = log_config.get("backup_count", 5)  # Default to

    rotating_log_file = Path(LOG_FOLDER) / Path(args.log_filename)
    log_folder_path = Path(LOG_FOLDER)
    # Create log folder if it does not exist
    if not log_folder_path.exists():
        try:
            log_folder_path.mkdir(parents=True)
            print(f"Log folder '{LOG_FOLDER}' created.")
        except OSError as e:
            print(f"Error creating log folder {LOG_FOLDER}: {e}")
            sys.exit(1)

    # These are the *actual* handlers that write to disk/console
    rotating_file_handler_real = logging.handlers.RotatingFileHandler(
        rotating_log_file.as_posix(), maxBytes=MAX_BYTES, backupCount=BACKUP_COUNT
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
            logger=logger,
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
