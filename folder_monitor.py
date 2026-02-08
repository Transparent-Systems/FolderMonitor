"""
Script: folder_monitor.py
Version: v2.0.0
Author: John Zoetebier
Requirements:
    1) rclone v1.64.2 (https://rclone.org/downloads/)
    2) Python 3.13.0 (https://www.python.org/downloads/)
    3) Python modules in requirements.txt
Usage:
    Run the following command to get help:
    python folder_monitor.py -h
Notes:
    See: README.md for more details.
Classes:
    MyEventHandler: Handles file system events and triggers rclone operations.
    MonitorHandler: Manages the observer and event handler lifecycle.
"""

import os
from pathlib import Path
import queue
import sys
import time
import yaml
import argparse
import logging
import logging.handlers


from version import __version__
from scripts.config_models import ConfigModels
from scripts.monitor_handler import MonitorHandler
from scripts.utils.logging_util import get_unique_logger
from scripts.backup_handler import BackupHandler
from scripts.command_processor import CommandProcessor

def configure_pid_file(pid_file_path: str) -> bool:
    """
    Configures the PID file for crash recovery.

    This function checks for the existence of a PID file. If it exists, it indicates
    a previous crash or unclean shutdown. It then creates a new PID file with the
    current process ID.

    Args:
        pid_file_path (str): The full path to the PID file.

    Returns:
        bool: True if a previous PID file was found (indicating a crash), False otherwise.
    """
    script_has_crashed = False

    # Write process ID to the crash PID file
    if os.path.exists(pid_file_path):
        logger.debug(
            f"Crash PID file '{pid_file_path}' already exists. This indicates a previous crash or an unclean shutdown."
        )
        script_has_crashed = True
    else:
        logger.debug(
            f"Crash PID file '{pid_file_path}' does not exist. Creating a new one."
        )
        logger.debug("This script will now enter normal run mode.")
        # Ensure the pid directory exists
        pid_dir = os.path.dirname(pid_file_path)
        if not os.path.exists(pid_dir):
            try:
                os.makedirs(pid_dir)
                logger.debug(f"PID directory '{pid_dir}' created.")
            except OSError as e:
                logger.debug(f"Error creating PID directory {pid_dir}: {e}")
                sys.exit(1)

    # Create the crash PID file with the current process ID
    # This is useful for crash recovery scenarios where the script was not stopped cleanly
    try:
        pid = os.getpid()  # Get the current process ID
        with open(pid_file_path, "w") as f:
            f.write(str(pid))
        logger.debug(f"Crash PID file: {pid_file_path} with PID {pid}")
    except OSError as e:
        logger.debug(f"Error creating crash PID file {pid_file_path}: {e}")
        sys.exit(1)
    # --- End Configuration for PID file ---
    return script_has_crashed


# Function to parse time strings like "1m", "5s", "1h"
# Returns seconds as an integer, or None if invalid/negative
def parse_time_string(time_str, default_value=None):
    """
    Parses a time string (e.g., "1m", "5s", "1h", "2d") and returns its value in seconds.

    Args:
        time_str (str): The time string to parse.
        default_value (int, optional): The default value to return if parsing fails
                                       or the string is invalid. Defaults to None.

    Returns:
        int: The time in seconds, or default_value if parsing fails.
    """

    if not isinstance(time_str, str) or not time_str:
        return default_value  # Handles missing or empty

    time_str = time_str.strip().lower()

    try:
        if time_str.endswith("s"):
            value = int(time_str[:-1])
        elif time_str.endswith("m"):
            value = int(time_str[:-1]) * 60
        elif time_str.endswith("h"):
            value = int(time_str[:-1]) * 3600
        elif time_str.endswith("d"):
            value = int(time_str[:-1]) * 86400
        else:
            value = default_value

        return value
    except ValueError:
        return default_value  # Handles unparseable strings


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="This script monitors changes on files and subfolders in the monitor folder."
    )
    # Argument for location of the configuration file
    parser.add_argument(
        "-c", "--config", 
        type=str, 
        default="conf/config.yaml",
        metavar="<PATH>", 
        help="Path to the configuration file"
    )

    # Argument for location of the log file
    parser.add_argument(
        "-l", "--log", 
        type=str, 
        default="conf/log.yaml",
        metavar="<PATH>", 
        help="Path to the log file"
    )

    # Add subcommands
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Version command
    subparsers.add_parser("version", help="Show version")
    # Test command
    test_parser = subparsers.add_parser("test", help="Run environment and configuration checks")
    test_parser.add_argument("-c", "--config", 
        type=str, 
        default="conf/config.yaml",
        metavar="<PATH>", 
        help="Path to the configuration file"
    )

    # Profile command
    profile_parser = subparsers.add_parser("profile", help="Manage profiles (subcommands: show, new, ... ; enter 'profile -h' for help)")
    profile_subparsers = profile_parser.add_subparsers(dest="profile_subcommand", help="Profile subcommands", required=True)
    
    # Profile subcommands
    profile_subparsers.add_parser("show", help="Show all profiles")
    profile_subparsers.add_parser("file", help="Show the file location of foldermonitor.conf")
    profile_subparsers.add_parser("import", help="Import all s3 profiles from rclone")
    profile_subparsers.add_parser("new", help="Create a new profile")
    profile_subparsers.add_parser("edit", help="Edit a profile")
    profile_subparsers.add_parser("delete", help="Delete a profile")
    profile_test_parser = profile_subparsers.add_parser("test", help="Test a profile")
    profile_test_parser.add_argument("-p", "--profile-name",
        type=str, 
        metavar="<NAME>", 
        help="Profile name of remote profile to test"
        )

    config_parser = subparsers.add_parser("config", help="Manage YAML configuration (subcommands: show, file, ... ; enter 'config -h' for help)")
    config_subparsers = config_parser.add_subparsers(dest="config_subcommand", help="Config subcommands", required=True)
    config_file_parser = config_subparsers.add_parser("file", help="Show location configuration file")
    config_file_parser.add_argument("-c", "--config", 
        type=str, 
        default="conf/config.yaml",
        metavar="<PATH>", 
        help="Path to the configuration file"
    )
    config_show_parser = config_subparsers.add_parser("show", help="Show monitor configurations")
    config_show_parser.add_argument("-c", "--config", 
        type=str, 
        default="conf/config.yaml",
        metavar="<PATH>", 
        help="Path to the configuration file"
    )

    args = parser.parse_args()

    # If log file does not exists, then we create one
    if (not os.path.exists(args.log)):
        print(f"Log configuration file '{args.log}' does not exist.")
        print(f"Creating new log configuration file '{args.log}'")
        with open(args.log, "w") as file:
            # Write version and logging configuration only
            file.write(f"version: {__version__[0]}.{__version__[1]}.{__version__[2]}\n")
            file.write("logging:\n")
            file.write("  file_name: folder_monitor.log\n")
            file.write("  folder: logs\n")
            file.write("  max_bytes: 10485760\n")
            file.write("  max_backup_count: 5\n")
            file.write("  # log_level: DEBUG | INFO | WARNING | ERROR | CRITICAL\n")
            file.write("  log_level: INFO\n")
            file.write("")

    # Load log configuration
    with open(args.log, "r") as file:
        log_config = yaml.safe_load(file)

    log_config = log_config.get("logging")
    if log_config is None:
        print(f"Configuration for 'logging' not found in {args.log}.")
        sys.exit(1)

    # --- Central Logging Setup (BEFORE ANY LoggingHandler INSTANCES ARE CREATED) ---
    log_queue = queue.Queue(-1)

    LOG_FILE = log_config.get("file_name", "folder_monitor.log")
    LOG_FOLDER = log_config.get("folder", "logs")
    MAX_BYTES = log_config.get("max_bytes", 10 * 1024 * 1024)  # Default to 10 MB
    BACKUP_COUNT = log_config.get("backup_count", 5)  # Default to

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
        rotating_log_file, maxBytes=MAX_BYTES, backupCount=BACKUP_COUNT
    )
    console_handler_real = logging.StreamHandler()

    formatter = logging.Formatter(
        "%(asctime)s - %(levelname)s - %(name)s - %(message)s"
    )
    rotating_file_handler_real.setFormatter(formatter)
    console_handler_real.setFormatter(formatter)

    # This is the handler that sends messages to the queue
    queue_handler = logging.handlers.QueueHandler(log_queue)

    # This listener takes messages from the queue and sends them to the real handlers
    queue_listener = logging.handlers.QueueListener(
        log_queue,
        rotating_file_handler_real,  # Pass the real file handler
        console_handler_real,  # Pass the real console handler
    )

    queue_listener.start()

    #
    # Configure the root logger to use the queue handler.
    # All log messages from any logger (including those created by LoggingHandler)
    # will propagate up to the root logger and then go through this queue_handler.
    root_logger = logging.getLogger()
    # Get log_level from log config

    log_level = log_config.get("log_level", "INFO")
    log_level = log_level.upper()
    root_logger.setLevel(log_level)
    # Remove default handlers if any (crucial for clean setup)
    for h in root_logger.handlers[:]:
        root_logger.removeHandler(h)

    root_logger.addHandler(queue_handler)
    # --- End Central Logging Setup ---

    # # Get a unique logger instance
    logger = get_unique_logger(log_level=log_level)

    # If config file does not exists, then we create one
    if (not os.path.exists(args.config)):
        print(f"App configuration file '{args.config}' does not exist.")
        print(f"Creating new app configuration file '{args.config}'")
        with open(args.config, "w") as file:
            # Write version and logging configuration only
            file.write(f"version: {__version__[0]}.{__version__[1]}.{__version__[2]}\n")
            file.write("monitors:\n")
            file.write("  - name: \"monitor-example\"\n")
            file.write("    monitor_path: \"/path/to/monitor\"\n")
            file.write("    remote_path: \"/path/to/remote\"\n")
            file.write("    remote_profiles:\n")
            file.write("      - \"profile-name-1\"\n")
            file.write("      - \"profile-name-2\"\n")
            file.write("      - \"profile-name-3\"\n")
            file.write("    backup:\n")
            file.write("        interval: \"24h\"\n")
            file.write("")


    # Load app configuration
    with open(args.config, "r") as file:
        monitor_config = yaml.safe_load(file)

    # Handle commands
    if args.command is not None:
        command_processor = CommandProcessor(logger=logger)
        config_path = Path(args.config).resolve()
        if args.command == "profile":
            profile_name = getattr(args, "profile_name", None)
            if profile_name is not  None:
                profile_name = profile_name.strip()
            # Put profile_name in dict object
            command_processor.process_command(
                command=args.command,
                subcommand=args.profile_subcommand,
                arguments={"profile_name" : profile_name}
                )
        elif args.command == "config":
            command_processor.process_command(
                command=args.command,
                subcommand=args.config_subcommand,
                arguments={"config_path" : config_path}
                )
        else:
            command_processor.process_command(
                command=args.command,
                arguments={"config_path" : config_path}
            )

        queue_listener.stop()
        logging.shutdown()      # Ensures all logs are written to disk
        sys.stdout.flush()      # Ensures all print statements hit the console
        os._exit(0)             # Suppress Python cleanup messages

    root_logger.setLevel(logging.DEBUG)  # Set the overall minimum logging level
    config_version = monitor_config.get("version")
    logger.debug(
        f"folder_monitor: setup logging ready. Log level: {log_config.get('log_level', 'INFO').upper()}"
    )
    logger.debug(f"Configuration version: {config_version}")

    # First validate monitor config file
    if not ConfigModels().validate(config_path=args.config, logger=logger):
        logger.error(
            f"Configuration file '{args.config}' is invalid. Exiting."
        )
        sys.exit(1)


    # --- Configuration for PID file ---
    CRASH_PID_FILE = "pid/crash_pid.txt"
    script_has_crashed = configure_pid_file(CRASH_PID_FILE)

    # --- Processing Monitors ---
    monitors = monitor_config.get("monitors")
    if monitors is None:
        logger.error(
            f"Configuration for 'monitors' not found in {args.config}."
        )
        sys.exit(1)

    logger.debug(f"Monitors found: {len(monitors)}")
    monitor_handlers = set()
    # Iterate over monitors, creating a MonitorHandler for each one and starting it
    for monitor in monitors:
        logger.debug(f"Processing monitor: {monitor['name']}")
        # Create a MonitorHandler instance for the current monitor
        monitor_handler = MonitorHandler(
            monitor_config=monitor,
            log_config=log_config,
        )

        monitor_handlers.add(monitor_handler)
        monitor_name = monitor['name']
        monitor_path = monitor['monitor_path']
        remote_path = monitor['remote_path']
        logger.info(
            f"Starting monitor for [{monitor_name}] at path [{monitor_path}] to remote_path: [{remote_path}]"
        )
        # Start the monitor
        monitor_handler.start_monitor()

    # BEGIN: backups
    logger.debug("Begin processing backups")
    backup_handlers = []
    for monitor in monitors:
        backup_handler = BackupHandler(
            logger=logger,
            monitor_config=monitor
        )
        
        backup_handler.start()
        backup_handlers.append(backup_handler)

    logger.debug("End processing backups")
    # END: backups

    # Keep the script running on the main thread
    # until interrupted by the user
    try:
        # Wait for interrupts or other exceptions
        logger.info("Folder monitor script is running. Press Ctrl+C to stop.")
        logger.info(
            "If script does not stop on Ctrl+C then a backup job might be running. Try again after the backup has finished."
        )
        while True:
            time.sleep(1)  # Sleep for a short duration to avoid busy-waiting
    except Exception as e:
        # logger.debug(f"Exception occurred: {e}")
        logger.error(f"Exception occurred: {e}")
    except KeyboardInterrupt:
        # logger.debug("KeyboardInterrupt received. Stopping the monitor...")
        logger.info("KeyboardInterrupt received. Stopping the monitor...")
    except SystemExit:
        # logger.debug("SystemExit received. Stopping the monitor...")
        logger.info("SystemExit received. Stopping the monitor...")
    finally:
        # Wait for all processes to finish
        logger.info("Waiting for all processes to finish...")
        for monitor_handler in monitor_handlers:
            monitor_handler.stop_monitor()
        logger.info("All monitor_handlers finished.")

    # Stop backup handlers
    for handler in backup_handlers:
        handler.stop()
    logger.info("All backup handlers finished.")

    # If the crash PID file exists, remove it
    if os.path.exists(CRASH_PID_FILE):
        logger.info(f"Removing crash PID file: {CRASH_PID_FILE}")
        os.remove(CRASH_PID_FILE)

    logger.info("Exiting folder_monitor script.")
    # Stop the queue listener
    logger.info("Stopping queue listener...")
    queue_listener.stop()
    sys.exit(0)