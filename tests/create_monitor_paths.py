"""
Version: 1.0

Create monitor_paths for test purposes.
Run this script before test_folder_monitor_integration to ensure each monitor can run properly with folder_monitor.
The script uses configuration file monitor yaml to get monitor_path for echa monitor.
"""

import argparse
import logging.handlers
import os
import sys
import logging
import yaml
import shutil

# Add the scripts directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../scripts')))

from utils import create_test_data, get_unique_logger, CheckPath, ProcessTestResult


  
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="This script creates all required monitor paths configured in a monotor yaml file.")
    parser.usage = "python test_monitor_handler_integration.py --monitor-config-path <path> --log-level <log level"
    parser.add_argument("--monitor-config-path", type=str, help="Path of monitor configuration file. Default is conf/monitor.yaml", default="tests/conf/monitor.yaml")
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

    log_config = monitor_config.get("logging")
    if log_config is None:
        print(f"Configuration for 'logging' not found in {args.monitor_config_path}.")
        sys.exit(1)

    LOG_FILE = log_config.get('log_filename', 'folder_monitor.log')
    LOG_FOLDER = log_config.get('log_folder', 'logs')
    MAX_BYTES = log_config.get('max_bytes', 10 * 1024 * 1024)  # Default to 10 MB
    BACKUP_COUNT = log_config.get('backup_count', 5)  # Default to

    rotating_log_file = os.path.join(LOG_FOLDER, "create_monitor_paths.log")
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
    # root_logger.addHandler(rotating_file_handler_real)
    logger = get_unique_logger(args.log_level)
    logger.debug("Processing monitors")
    monitors = monitor_config.get("monitors")

    # Iterate over monitors, and create monitor_path if not exists
    for monitor in monitors:
        logger.debug(f"Checking monitor path for monitor: [{monitor['name']}]")

        if not monitor.get("enabled"):
            logger.debug(f"Monitor {monitor['name']} is disabled. Skipping...")
            continue

        # Create monitor_path if not exists
        monitor_path = monitor.get("monitor_path")
        logger.info(f"Checking monitor path [{monitor_path}]")
        if (not os.path.exists(monitor_path)):
            file_path = create_test_data(path=monitor_path, files=[])
            logger.info(f"Created monitor path {file_path}")

    logger.info(f"===> Ready creating monitor paths, if not exists <===")
