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
from rclone_handler import RcloneHandler


# Function to parse time strings like "1m", "5s", "1h"
# Returns seconds as an integer, or None if invalid/negative
def parse_time_string(time_str):
    if not isinstance(time_str, str) or not time_str:
        return None # Handles missing or empty
    
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
            value = int(time_str) # Allow raw numbers (e.g., "30" for 30 seconds)

        if value < 0:
            return None # Handles negative intervals
        return value
    except ValueError:
        return None # Handles unparseable strings

# Perform backup
def perform_backup(monitor_config, rclone_handler, reason="scheduled"):
    monitor_name = monitor_config["name"]
    logger.debug(f"[{monitor_name}] Performing {reason} backup at {time.ctime()} for: {monitor_config['monitor_path']} -> {monitor_config['destination_path']}")
    # Use rclone_handler for backup operations
    # This will also trigger and event for all files backed up in the corresponding monitor
    # That is expected behaviour of rclone_handler.copy()
    # The monitor needs to run while backup is running in order to handle events
    rclone_handler.copy(
        source_path=monitor_config["monitor_path"],
        is_directory=True,  # Assuming monitor_path is a directory
    )

# This is the function that each thread will execute
def monitor_backup_task(monitor_config, is_crash_recovery=False):
    monitor_name = monitor_config["name"]
    raw_interval = monitor_config.get("backup_interval")
    interval_seconds = parse_time_string(raw_interval)

    destination_path = monitor_config.get("destination_path")
    base_path = monitor_config.get("base_path", "")
    copy_mode = monitor_config.get("copy_mode", "copy") # Default to "copy"
    rclone_handler = RcloneHandler(destination_path, base_path, copy_mode, logger)

    # Determine the effective interval and behavior based on crash recovery and config
    if is_crash_recovery:
        logger.debug(f"[{monitor_name}] Server crash detected. Forcing one-off backup.")
        perform_backup(monitor_config, rclone_handler, reason="crash recovery")
        rclone_handler = None # Clean up the rclone handler
        return # Exit the thread after one-off backup
    elif interval_seconds is None or interval_seconds < 0: # This check is redundant due to parse_time_string but good for clarity
        logger.debug(f"[{monitor_name}] Backup interval is missing, empty, or negative ('{raw_interval}'). No recurring backup will be performed.")
        rclone_handler = None # Clean up the rclone handler
        return # Exit the thread if no valid interval for recurring backup
    elif interval_seconds == 0:
        logger.debug(f"[{monitor_name}] Backup interval is 0. Performing one-off backup.")
        perform_backup(monitor_config, rclone_handler, reason="one-off (interval 0)")
        rclone_handler = None # Clean up the rclone handler
        return # Exit the thread after one-off backup
    else:
        logger.debug(f"[{monitor_name}] Monitor started. Next scheduled backup in {interval_seconds} seconds.")
        # No immediate backup. The first backup will occur after the initial delay.
        # This loop will run indefinitely for recurring backups
        while True:
            time.sleep(interval_seconds)
            perform_backup(monitor_config, rclone_handler, reason="scheduled")


def check_for_crash_pin():
    return os.path.exists(CRASH_PIN_FILE)


# Create a unique logger instance with a name based on UUID import uuid
def get_unique_logger(log_config):
    # Get globally unique logger name
    logger_name = f"Logger_{uuid.uuid4()}"
    logger = logging.getLogger(logger_name)
    
    # Set the logger to debug level initially for its internal setup messages.
    # The effective level will also be governed by the root logger's level.
    logger.setLevel(logging.DEBUG) 
    log_level_str = log_config.get('log_level', 'INFO').upper() # Default to INFO if not specified
    level_map = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL
    }
    logger.setLevel(level_map.get(log_level_str, logging.NOTSET)) # Use .get with default for robustness
    return logger


class ConfigHandler:
    def __init__(self, monitor_config_path):
        with open(monitor_config_path, 'r') as file:
            self.config = yaml.safe_load(file)

    def get_config(self, config_key):
        return self.config.get(config_key)
  


class MyEventHandler(FileSystemEventHandler):
    """
    A custom event handler that processes file system events and triggers rclone operations.
    This class is designed to handle file creation, deletion, modification, and movement events.
    Args:
        rclone_handler (RcloneHandler): An instance of RcloneHandler to perform file operations.
        logger (logging.Logger): An optional logger instance for logging events. If not provided, a default logger is created.
    Examples:
        >>> rclone_handler = RcloneHandler("e2:/test-foldermonitor/Test", "Test", True, logger)
        >>> event_handler = MyEventHandler(rclone_handler, logger)
    """

    def __init__(self, rclone_handler, logger=None):
        self.rclone_handler = rclone_handler
        self.logger = logger if logger else logging.getLogger(__name__)
        self.logger.debug("MyEventHandler initialized")
       
    def on_created(self, event):
        self.logger.info(f"on_created: {event.src_path}, event.is_directory: {event.is_directory}")
        self.rclone_handler.copy(event.src_path, event.is_directory)

    def on_deleted(self, event):
        self.logger.info(f"on_deleted: {event.src_path}, event.is_directory: {event.is_directory}")
        self.rclone_handler.delete(event.src_path, event.is_directory)

    def on_modified(self, event):
        self.logger.info(f"on_modified: {event.src_path}, event.is_directory: {event.is_directory}")
        self.rclone_handler.copy(event.src_path, event.is_directory)

    def on_moved(self, event):
        self.logger.info(f"on_moved - renamed from {event.src_path} to {event.dest_path}")
        self.rclone_handler.delete(event.src_path, event.is_directory)
        self.rclone_handler.copy(event.dest_path, event.is_directory)

    def __del__(self):
        self.logger.info("Event handler closed")
        self.rclone_handler = None


class MonitorHandler:
    """
    A class to monitor a folder for changes and trigger rclone operations.  
    The class has been tested with Python >= 3.10 and rclone v1.64.2.
    Args:
        monitor_config (dictionary): The monitor configuration dictionary configured in the monitor yaml file
        logging_config (dictionary): The logging configuration dictionary configured on the monitor yaml file
    """
    def __init__(self, monitor_config, logging_config):
        self.monitor_config = monitor_config
        self.logging_config = logging_config
        self.monitor_running = False        
        self.observer = None
        # # Create LoggingHandler instance
        # self.logging_handler = LoggingHandler(
        #     log_config=logging_config,
        # )

        self.logger = get_unique_logger(logging_config)

        if monitor_config.get('enabled') is False:
            self.logger.debug("Monitor is disabled. Exiting MonitorHandler __init__")
            return

        self.monitor_path = monitor_config.get('monitor_path')
        if not self.monitor_path:
            raise ValueError("monitor_path is required in the monitor configuration.")
        
        # If monitor_path does not exist, then raise an error
        if not os.path.exists(self.monitor_path):
            raise FileNotFoundError(f"Monitor path '{self.monitor_path}' does not exist. Please check the configuration.")
        
        self.destination_path = monitor_config.get('destination_path')
        if not self.destination_path:
            raise ValueError("destination_path is required in the monitor configuration.")
        
        self.base_path = monitor_config.get('base_path', '')
        self.copy_mode = monitor_config.get('copy_mode', 'copy')
        self.monitor_running = True
        self.logger.debug("MonitorHandler: exiting __init__")


    def start_monitor(self):
        """Start monitoring the specified folder for changes."""
        rclone_handler = RcloneHandler(self.destination_path, self.base_path, self.copy_mode, self.logger)
        event_handler = MyEventHandler(rclone_handler, self.logger)
        self.observer = Observer()
        self.observer.schedule(event_handler, self.monitor_path, recursive=True)
        self.observer.start()
        self.logger.info(f"Observer {self.observer.name} started on folder {self.monitor_path}")

    def stop_monitor(self):
        logger.info(f"Stopping monitor for {self.monitor_path}")
        if self.observer is not None:
            self.observer.stop()
            self.observer.join()
            self.logger.info("Monitor stopped.")
            self.observer = None

    
if __name__ == "__main__":
    print("This is file_monitor script running directly.")
    parser = argparse.ArgumentParser(description="This script monitors changes on files and subfolders in the monitor folder.")
    parser.usage = "python folder_monitor.py --monitor-config-path <path>"
    parser.add_argument("--monitor-config-path", type=str, help="Path of monitor configuration file. Default is conf/monitor.yaml", default="conf/monitor.yaml")
    args = parser.parse_args()

    # --- Configuration for PIN file ---
    CRASH_PIN_FILE = "crash_pin.txt"

    # Load configuration from the monitor config file
    config_handler = ConfigHandler(args.monitor_config_path)
    logging_config = config_handler.get_config("logging")
    if logging_config is None:
        print(f"Configuration for 'folder_monitor' not found in {args.monitor_config_path}.")
        sys.exit(1)


    # --- Central Logging Setup (BEFORE ANY LoggingHandler INSTANCES ARE CREATED) ---
    log_queue = queue.Queue(-1)

    LOG_FILE = logging_config.get('log_file', 'folder_monitor.log')
    LOG_FOLDER = logging_config.get('log_folder', 'logs')
    MAX_BYTES = logging_config.get('max_bytes', 10 * 1024 * 1024)  # Default to 10 MB
    BACKUP_COUNT = logging_config.get('backup_count', 5)  # Default to

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
    logger = get_unique_logger(logging_config)
    logger.debug(f"folder_monitor: start processing configured monitors")

    monitors = config_handler.get_config("monitors")
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
            logging_config=logging_config,
        )

        if not monitor_handler.monitor_running:
            logger.debug(f"Monitor {monitor['name']} is disabled. Skipping...")
            continue

        monitor_handlers.add(monitor_handler)
        logger.info(f"Starting monitor for [{monitor['name']}] at path {monitor['monitor_path']}")
        # Start the monitor        
        monitor_handler.start_monitor()


    # BEGIN: backups
    is_crash_recovery_mode = check_for_crash_pin()
    if is_crash_recovery_mode:
        logger.debug(f"--- CRASH PIN DETECTED: {CRASH_PIN_FILE} --- Entering Crash Recovery Mode ---")
    else:
        logger.debug("--- No crash PIN detected. Operating in normal mode. ---")

    active_threads = []

    monitor_paths = set()
    for monitor in monitors:
        #     # Do not trigger a backup for the same monitor_folder twice
        if monitor.get("monitor_path") in monitor_paths:
            continue

        monitor_paths.add(monitor.get("monitor_path"))

        # Only run backup if monitor is enabled
        if monitor.get("enabled", True): # Default to enabled if not specified
            thread = threading.Thread(
                target=monitor_backup_task,
                args=(monitor, is_crash_recovery_mode), # Pass crash recovery flag
                daemon=True
            )
            thread.start()
            active_threads.append(thread)
            logger.debug(f"Initiated processing for monitor: {monitor['name']}")
        else:
            logger.debug(f"Monitor '{monitor['name']}' is explicitly disabled.")

    # END: backups

    logger.debug("\nAll monitor threads initiated. Press Ctrl+C to exit.")

    # Keep the script running on the main thread
    # until interrupted by the user          
    try:
        while True:
            time.sleep(1)  # Sleep for a short duration to avoid busy-waiting
            # Update modification time of monitor root folder every backup_interval
            # monitor_paths = set()
            # for monitor_handler in monitor_handlers:
            #     # Do not trigger a backup for the same monitor_folder twice
            #     if monitor_handler.monitor_path in monitor_paths:
            #         continue

            #     monitor_paths.add(monitor_handler.monitor_path)
            #     if  not monitor_handler.monitor_running:
            #         continue

            #     # Update the modification time of the monitor path to trigger a backup
            #     # This is safeguard for when the monitor has been interrupted while in the middle of processing changes
            #     update_folder_modification_time(monitor_handler.monitor_path)
            #     logger.debug(f"Updating modification time for {monitor_handler.monitor_path}")
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
              
    # If the crash PIN file exists, remove it
    if os.path.exists(CRASH_PIN_FILE):
       logger.info(f"Removing crash PIN file: {CRASH_PIN_FILE}")
       os.remove(CRASH_PIN_FILE) 

    logger.info("Exiting folder_monitor script.")
    # Stop the queue listener
    logger.info("Stopping queue listener...")
    queue_listener.stop()
    sys.exit(0)

