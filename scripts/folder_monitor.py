"""
Script: folder_monitor.py
Version: v1.0.0
Author: John Zoetebier
Date: 2025-05-10
    It logs the type of change and the file path to both the console and a log file.
    The script utilizes the rclone_handler module to copy or delete files and folders using rclone.
    Designed to run indefinitely, it monitors the specified folder for changes until interrupted by the user (Ctrl+C).
    The script is compatible with both Windows and Linux systems.
Requirements:
    1) rclone v1.64.2 (https://rclone.org/downloads/)
    2) Python 3.13.0 (https://www.python.org/downloads/)
    3) Python modules in requirements.txt
Usage:
    Example:
    python folder_monitor.py
    python folder_monitor.py --monitor-config-path conf/monitor.yaml

    Arguments:
        --monitor-config-path: Path to monitor configuration file. Default path is ../conf/monitor.yaml.
Notes:
    - Ensure you have the necessary permissions to access the monitored folder.
    - It is recommended to use a virtual Python environment to avoid conflicts with other packages.
    - To create and activate a virtual environment:
        python -m venv .venv
        ./.venv/Scripts/Activate.ps1  (Windows)
        source .venv/bin/activate  (macOS/Linux)
    - After Python has been installed you can install required modules with:
        pip install -r requirements.txt
Classes:
    MyEventHandler: Handles file system events and triggers rclone operations.
    MonitorHandler: Manages the observer and event handler lifecycle.
Entry Point:
    Parses command-line arguments, initializes logging and monitoring, and keeps the script running until interrupted.
"""

import os
import queue
import sys
import threading
import time
import yaml
import argparse
import logging
import uuid

from logging.handlers import RotatingFileHandler
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from watchdog.events import FileSystemEvent, FileCreatedEvent, FileDeletedEvent, FileModifiedEvent, FileMovedEvent, DirCreatedEvent, DirDeletedEvent, DirMovedEvent, DirModifiedEvent, FileClosedEvent
from rclone_handler import RcloneHandler
from monitor_handler import MonitorHandler
from utils import get_unique_logger


def configure_pid_file(pid_file_path):
    # --- Configuration for PID file ---
    script_has_crashed = False

    # Write process ID to the crash PID file
    if os.path.exists(pid_file_path):
        logger.debug(f"Crash PID file '{pid_file_path}' already exists. This indicates a previous crash or an unclean shutdown.")
        script_has_crashed = True
    else:
        logger.debug(f"Crash PID file '{pid_file_path}' does not exist. Creating a new one.")
        logger.debug("This script will now enter normal mode.")
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
        with open(pid_file_path, 'w') as f:
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
    if not isinstance(time_str, str) or not time_str:
        return default_value # Handles missing or empty
    
    time_str = time_str.strip().lower()

    try:
        if time_str.endswith('s'):
            value = int(time_str[:-1])
        elif time_str.endswith('m'):
            value = int(time_str[:-1]) * 60
        elif time_str.endswith('h'):
            value = int(time_str[:-1]) * 3600
        elif time_str.endswith('d'):
            value = int(time_str[:-1]) * 86400
        else:
            value = default_value

        return value
    except ValueError:
        return default_value # Handles unparseable strings

# Perform backup
def perform_backup(monitor_config, reason="scheduled"):
    monitor_name = monitor_config["name"]
    logger.debug(f"Performing {reason} backup for monitor [{monitor_name}] at {time.ctime()} for: {monitor_config['monitor_path']} -> {monitor_config['destination_path']}")
    # Use rclone_handler for backup operations
    # Check if backup_mode is copy or sync
    backup_config = monitor_config.get("backup", {})
    backup_mode = backup_config.get("backup_mode", "copy")  # Default to "copy" if not specified

    if backup_mode not in ["copy", "sync"]:
        logger.debug(f"Invalid backup_mode '{backup_mode}' for monitor '{monitor_name}'. Defaulting to 'copy'.")
        backup_mode = "copy"

    destination_path = monitor_config.get("destination_path")
    monitor_path = monitor_config.get("monitor_path")
    rclone_flags = monitor_config.get("rclone_flags", "")
    rclone_handler = RcloneHandler(destination_path, monitor_path, logger, rclone_flags)

    if backup_mode == "sync":
        logger.debug(f"Syncing folder for monitor [{monitor_name}] from {monitor_config['monitor_path']} to {destination_path}")
        rclone_handler.sync_folder(
            source_path=monitor_config["monitor_path"]
        )
    else:  # Default to "copy"
        logger.debug(f"Copying folder for monitor [{monitor_name}] from {monitor_config['monitor_path']} to {destination_path}")
        rclone_handler.copy_folder(
            source_path=monitor_config["monitor_path"]
        )

    rclone_handler = None # Clean up the rclone handler


# This is the function that each thread will execute
def monitor_backup_task(monitor_config, is_crash_recovery=False):
    monitor_name = monitor_config["name"]
    backup_config = monitor_config.get("backup", {})
    if not backup_config:
        logger.debug(f"No backup configuration found for '{monitor_name}'")
        return  # Exit if no backup configuration is present
    
    if backup_config.get("enabled", True) is False:
        logger.debug(f"Backup for monitor '{monitor_name}' is disabled. Skipping backup task.")
        return  # Exit if backup is explicitly disabled
    
    raw_interval = backup_config.get("interval", "0")  # Default to "0" if not specified
    interval_seconds = parse_time_string(raw_interval,0)  # Default to 0 if parsing fails

    # Determine the effective interval and corresponding behavior
    # The logic for determining the backup interval is as follows:
    # - If the interval is None or 0, a one-off backup will be performed immediately.
    # - If the interval is positive, a recurring backup will be performed at the specified interval.
    # Check for None first to avoid TypeError when comparing with integers

    if  interval_seconds == None:
        logger.debug(f"[{monitor_name}] Backup interval is empty or missing. Set backup interval to 0.")
        interval_seconds = 0  # Treat None as 0 for one-off backup

    if  interval_seconds == 0:
        logger.debug(f"[{monitor_name}] Backup interval is 0. Performing one-off backup.")
        perform_backup(monitor_config, reason="one-off (interval 0)")
        return # Exit the thread after one-off backup
    
    one_hour = parse_time_string("1h")
    if interval_seconds < one_hour:
        logger.info (f"Minimum backup interval is one hour: {one_hour} seconds")
        interval_seconds = one_hour
    
    logger.debug(f"[{monitor_name}] Backup scheduled every {interval_seconds} seconds.")
    # This loop will run indefinitely for recurring backups
    while True:
        perform_backup(monitor_config, reason="scheduled")
        time.sleep(interval_seconds)

   
if __name__ == "__main__":
    print("This is file_monitor script running directly.")
    parser = argparse.ArgumentParser(description="This script monitors changes on files and subfolders in the monitor folder.")
    parser.usage = "python folder_monitor.py --monitor-config-path <path>"
    parser.add_argument("--monitor-config-path", type=str, help="Path of monitor configuration file. Default is conf/monitor.yaml", default="conf/monitor.yaml")
    args = parser.parse_args()

    # Load configuration from the monitor config file
    # monitor_config = ConfigHandler(args.monitor_config_path)
    with open(args.monitor_config_path, 'r') as file:
        monitor_config = yaml.safe_load(file)

    log_config = monitor_config.get("logging")
    if log_config is None:
        print(f"Configuration for 'logging' not found in {args.monitor_config_path}.")
        sys.exit(1)

        # --- Central Logging Setup (BEFORE ANY LoggingHandler INSTANCES ARE CREATED) ---
    log_queue = queue.Queue(-1)

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
        rotating_file_handler_real, # Pass the real file handler
        console_handler_real        # Pass the real console handler
    )

    queue_listener.start()

    # 
    # Configure the root logger to use the queue handler.
    # All log messages from any logger (including those created by LoggingHandler)
    # will propagate up to the root logger and then go through this queue_handler.
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG) # Set the overall minimum logging level
    # Remove default handlers if any (crucial for clean setup)
    for h in root_logger.handlers[:]:
        root_logger.removeHandler(h)

    root_logger.addHandler(queue_handler)
    root_logger.debug("Root logger configured with queue handler.")
    # --- End Central Logging Setup ---

    # # Get a unique logger instance
    logger = get_unique_logger(log_level=log_config.get("log_level"))
    logger.debug(f"folder_monitor: setup logging ready. Log level: {log_config.get('log_level', 'INFO').upper()}")
    config_version = monitor_config.get("version")
    logger.debug(f"Configuration version: {config_version}")

    # --- Configuration for PID file ---
    CRASH_PID_FILE = "pid/crash_pid.txt"
    (script_has_crashed) = configure_pid_file(CRASH_PID_FILE)

    # --- Processing Monitors ---
    monitors = monitor_config.get("monitors")
    if monitors is None:
        logger.error(f"Configuration for 'monitors' not found in {args.monitor_config_path}.")
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

        if not monitor_handler.monitor_enabled:
            logger.debug(f"Monitor {monitor['name']} is disabled. Skipping...")
            continue

        monitor_handlers.add(monitor_handler)
        logger.info(f"Starting monitor for [{monitor['name']}] at path [{monitor['monitor_path']}] to destination: [{monitor['destination_path']}]")
        # Start the monitor        
        monitor_handler.start_monitor()


    # BEGIN: backups
    logger.debug("Begin processing backups")
    active_threads = []
    for monitor in monitors:
        # Backup runs if backup is enabled, regardless if monitor enabled or not
        thread = threading.Thread(
            target=monitor_backup_task,
            args=(monitor, ), # Trailing "," requireed as args expects an Iterable
            daemon=True
        )
        thread.start()
        active_threads.append(thread)

    logger.debug("End processing backups")
    # END: backups

    # Keep the script running on the main thread
    # until interrupted by the user          
    try:
        # Wait for interrupts or other exceptions
        logger.info("Folder monitor script is running. Press Ctrl+C to stop.")
        logger.info("If script does not stop on Ctrl+C then a backup job might be running. Try again after the backup has finished.")
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

    for thread in active_threads:
        if thread.is_alive():
            logger.info(f"Waiting for thread {thread.name} to finish...")
            thread.join()
            thread = None
    logger.info("All threads finished.")
              
    # If the crash PID file exists, remove it
    if os.path.exists(CRASH_PID_FILE):
       logger.info(f"Removing crash PID file: {CRASH_PID_FILE}")
       os.remove(CRASH_PID_FILE) 

    logger.info("Exiting folder_monitor script.")
    # Stop the queue listener
    logger.info("Stopping queue listener...")
    queue_listener.stop()
    sys.exit(0)

