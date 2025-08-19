"""
Version: 1.0

Create monitor_paths for test purposes.
Run this script before test_folder_monitor_integration to ensure each monitor can run properly with folder_monitor.
The script uses configuration file monitor yaml to get monitor_path for echa monitor.
"""

import argparse
import logging.handlers
from pathlib import Path
import sys
import logging
import yaml

# Add the scripts directory to the Python path
scriptspath = Path(__file__).parent / Path("../scripts")
sys.path.insert(0, scriptspath.resolve().as_posix())

from utils.logging_util import (
    get_unique_logger,
)
from utils.testing_util import (
    ProcessTestResult,
)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="This script creates all required monitor paths configured in a monotor yaml file."
    )
    parser.usage = "python test_monitor_handler_integration.py --config-path <path> --log-level <log level"
    parser.add_argument(
        "--config-path",
        type=str,
        help="Path of monitor configuration file. Default is conf/config.yaml",
        default="conf/config.tests.yaml",
    )
    parser.add_argument(
        "--log-level", type=str, help="Log level. Default is DEBUG", default="DEBUG"
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

    # Load configuration from the monitor config file
    with open(args.config_path, "r") as file:
        monitor_config = yaml.safe_load(file)

    log_config = monitor_config.get("logging")
    if log_config is None:
        print(f"Configuration for 'logging' not found in {args.config_path}.")
        sys.exit(1)

    LOG_FILE = log_config.get("log_filename", "folder_monitor.log")
    LOG_FOLDER = log_config.get("log_folder", "logs")
    MAX_BYTES = log_config.get("max_bytes", 10 * 1024 * 1024)  # Default to 10 MB
    BACKUP_COUNT = log_config.get("backup_count", 5)  # Default to

    rotating_log_file = Path(LOG_FOLDER) / Path("create_monitor_paths.log")
    # Create log folder if it does not exists
    log_folder_path = Path(LOG_FOLDER)
    try:
        if not log_folder_path.exists():
            log_folder_path.mkdir(parents=True)
    except OSError as e:
        print(f"Error creating log folder {LOG_FOLDER}: {e}")
        sys.exit(1)

    # These are the *actual* handlers that write to disk/console
    rotating_file_handler_real = logging.handlers.RotatingFileHandler(
        rotating_log_file, maxBytes=MAX_BYTES, backupCount=BACKUP_COUNT
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
        monitor_path = Path(monitor.get("monitor_path"))
        logger.info(f"Checking monitor path [{monitor_path}]")
        if not monitor_path.exists():
            monitor_path.mkdir(parents=True)
            logger.info(f"Created monitor path {monitor_path}")

    logger.info(f"===> Ready creating monitor paths, if not exists <===")
