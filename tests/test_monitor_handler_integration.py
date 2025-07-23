import argparse
import os
import sys
import logging
import shutil

# Add the scripts directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../scripts')))

from folder_monitor import MonitorHandler, ConfigHandler

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


def run_integration_check(monitor_config : {}, logger = None):
    logger.debug("--- Rclone Integration Check ---")
    handler = MonitorHandler(monitor_config, logger)

    try:

        # Test 1: Create new file
        logger.debug(f"\n3. Copying a test file to '{test_remote}'...")
        file_path = f"{src_path}/monitor_handler/Subfolder1/test1.txt"
        # handler is instantiated with destination_path. Method copy_file derives destination path from the src_path.
        # Path in scr_path after base_path is appended to destination path
        (result_code, result_output) = handler.copy_file(file_path)
        logger.debug(f"Copy_file output:\n{result_output}")
        assert result_code == 0

        # # Test 4: Verify file existence on remote (using lsf)
        # logger.debug("Verifying file on remote...")
        # file_path = f"{src_path}/monitor_handler/Subfolder1/test1.txt"
        # dst_path = get_destination_path(file_path, base_path, destination_path)
        # rclone_command = f"lsf, {dst_path}"
        # (result_code, result_output) = handler.run_command(rclone_command)
        # logger.debug(f"Remote content:\n{result_output}")
        # file_name = os.path.basename(file_path)
        # assert file_name in result_output

        # # Test 5: Create a new file
        # logger.debug("Create a new file on remote...")
        # file_path = create_test_data(src_path, "monitor_handler/Subfolder1/test3.txt")
        # (result_code, result_output) = handler.copy_file(file_path)
        # logger.debug(f"Copy result code: {result_code}")
        # assert result_code == 0

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

        # Test 7: Copy entire folder
        logger.debug("Copy entire folder to destination ...")
        test_files = []
        test_files.append("monitor_handler/Subfolder3/test1.txt")
        test_files.append("monitor_handler/Subfolder3/test2.txt")
        file_path = create_test_data(src_path, test_files)
        head = os.path.dirname(file_path)
        (result_code, result_output) = handler.copy_folder(head)
        logger.debug(f"Copy result code: {result_code}")
        assert result_code == 0

        # Check if subolder has been copied to destination
        rclone_command = ["lsf", "--format", "tshp", "--separator", " | ", head] 
        (result_code, result_output) = handler.run_command(rclone_command)
        logger.debug(f"result_output:\n{result_output}")
        file_name = os.path.basename(file_path)
        assert file_name in result_output

        # Test 8: Remove entire folder and contents from destination
        logger.debug("Remove entire folder and contents from destination ...")
        test_files = []
        test_files.append("monitor_handler/Subfolder3/test1.txt")
        test_files.append("monitor_handler/Subfolder3/test2.txt")
        file_path = create_test_data(src_path, test_files)
        head = os.path.dirname(file_path)
        (result_code, result_output) = handler.delete_folder(head)
        assert result_code == 0

        # Check if subolder has been removed from destination
        dst_path = get_destination_path(head, base_path, destination_path)
        rclone_command = ["lsf", "--format", "tshp", "--separator", " | ", dst_path] 
        (result_code, result_output) = handler.run_command(rclone_command)
        assert result_code == 0
        file_name = os.path.basename(file_path)
        assert file_name not in result_output


        logger.debug("\n--- All integration checks passed! ---")

    except Exception as e:
        logger.debug(f"\n--- Integration check FAILED: {e} ---")
    finally:
        logger.debug(f"\n--- Integration check cleanup")
        # if os.path.exists(local_file_path):
        #     os.remove(local_file_path)


def create_test_data(path: str, files: list[str] | str):
    """
    Create files relative to path
    """
    # try:
    #     os.makedirs(path, exist_ok=True)
    # except OSError as e:
    #     logger.debug(f"Error creating path {path}: {e}")
    #     sys.exit(1)

    if isinstance(files, str):
        file_list = [f"{files}"]
    else:
        file_list = files

    # file_path = ""
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

   
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="This script runs integration tests for a monitor configured in a monotor yaml file.")
    parser.usage = "python test_monitor_handler_integration.py --monitor-config-path <path>"
    parser.add_argument("--monitor-config-path", type=str, help="Path of monitor configuration file. Default is conf/monitor.yaml", default="tests/conf/monitor.yaml")
    args = parser.parse_args()

    test_files = []
    test_files.append("Source/Cloud/monitor_handler/test1.txt")
    test_files.append("Source/Cloud/monitor_handler/test2.txt")
    test_files.append("Source/Cloud/monitor_handler/Subfolder1/test1.txt")
    test_files.append("Source/Cloud/monitor_handler/Subfolder1/test2.txt")
    test_files.append("Source/Cloud/monitor_handler/Subfolder2/test1.txt")
    test_files.append("Source/Cloud/monitor_handler/Subfolder2/test2.txt")
    # create_test_data(path, test_files)

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
 
    # Load monitor.yaml
    # Load configuration from the monitor config file

    config_handler = ConfigHandler(args.monitor_config_path)
    log_config = config_handler.get_config("logging")
    if log_config is None:
        print(f"Configuration for 'logging' not found in {args.monitor_config_path}.")
        sys.exit(1)

    LOG_FILE = log_config.get('log_file_name', 'folder_monitor.log')
    LOG_FOLDER = log_config.get('log_folder', 'logs')
    MAX_BYTES = log_config.get('max_bytes', 10 * 1024 * 1024)  # Default to 10 MB
    BACKUP_COUNT = log_config.get('backup_count', 5)  # Default to

    rotating_log_file = os.path.join(LOG_FOLDER, LOG_FILE)
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
    logger = logging.getLogger()
    logger.debug("Before calling run_integration_check")

    monitors = config_handler.get_config("monitors")

    monitor_handlers = set()
    # Iterate over monitors, creating a MonitorHandler for each one and starting it
    for monitor in monitors:
        logger.debug(f"Processing monitor: [{monitor['name']}]")
        # Create a MonitorHandler instance for the current monitor
        monitor_handler = MonitorHandler(
            monitor_config=monitor,
            log_config=log_config,
        )

        if not monitor_handler.monitor_enabled:
            logger.debug(f"Monitor {monitor['name']} is disabled. Skipping...")
            continue

        monitor_handlers.add(monitor_handler)
        logger.info(f"Starting monitor for [{monitor['name']}] at path {monitor['monitor_path']}")
        # Start the monitor        
        monitor_handler.start_monitor()

    # This is where we trigger events on a monitor
    # run_integration_check(monitor, logger)

    # Wait for all processes to finish
    logger.info("Waiting for all processes to finish...")
    for monitor_handler in monitor_handlers:
        monitor_handler.stop_monitor()
    logger.info("All monitor_handlers finished.")
