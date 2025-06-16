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
    python folder_monitor.py --monitor-path "D:\\Cloud\\Test" --base-path "Cloud" --destination-path "e2:test-zoetebier-net/Cloud" --sync-mode True

    Arguments:
        --monitor-path:        Path to the folder to monitor for changes.
        --base-path:           The path in monitor-path after base-path is appended to the destination-path. Default is ''.
        --destination-path:    Destination path, usually a folder on remote cloud storage.
        --sync-mode:           Allow deletion of files and folders on the destination path. Default is False.
        --monitor-config-path: Path to monitor configuration file. Default path is ../conf/monitor.yaml.
Notes:
    - Ensure you have the necessary permissions to access the monitored folder.
    - It is recommended to use a virtual Python environment to avoid conflicts with other packages.
    - To create and activate a virtual environment:
        python -m venv .venv
        .\.venv\Scripts\Activate.ps1  (Windows)
        source .venv/bin/activate  (macOS/Linux)
    - After Python has been installed you can install required modules with:
        pip install -r requirements.txt
Classes:
    MyEventHandler: Handles file system events and triggers rclone operations.
    MonitorHandler: Manages the observer and event handler lifecycle.
Entry Point:
    Parses command-line arguments, initializes logging and monitoring, and keeps the script running until interrupted.
"""

import sys
import time
import yaml
import argparse
import logging
from logging.handlers import RotatingFileHandler

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from logging_handler import LoggingHandler
from rclone_handler import RcloneHandler


class MyEventHandler(FileSystemEventHandler):
    """
    A custom event handler that processes file system events and triggers rclone operations.
    This class is designed to handle file creation, deletion, modification, and movement events.
    Args:
        rclone_handler (RcloneHandler): An instance of RcloneHandler to perform file operations.
        logger (logging.Logger): An optional logger instance for logging events. If not provided, a default logger is created.
    Examples:
        >>> rclone_handler = RcloneHandler("e2:/test-zoetebier-net/Test", "Test", True)
        >>> event_handler = MyEventHandler(rclone_handler)
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
        # Delete from file or folder at destination
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
        monitor_path (str): The path of the folder to monitor for changes.
        destination_path (str): The destination path, usually a folder on remote cloud storage.
        base_path (str): A path or folder name. Everything after base-path is copied to the destination or deleted from the destination. Default is ''.
        sync_mode (str): Allow deletion of files and folders on the destination path. Default is "False".
        monitor_config_path (str): Path of monitor configuration file. Default is "../conf/monitor.yaml".
    Examples:
        >>> monitor_handler = MonitorHandler(
                monitor_path="D:/Cloud/Test",
                destination_path="e2:test-zoetebier-net/Cloud",
                base_path="Cloud",
                sync_mode="True",
                monitor_config_path="../conf/monitor.yaml"
            )
        >>> monitor_handler.start_monitor()
    """
    def __init__(self, monitor_path, destination_path, base_path="", sync_mode="False", monitor_config_path="../conf/monitor.yaml"):
        self.monitor_path = monitor_path
        self.destination_path = destination_path
        self.base_path = base_path
        self.sync_mode = sync_mode
        self.monitor_config_path = monitor_config_path
        self.observer = None

        # Ensure logging_handler is an instance variable, otherwise it will be garbage collected and the logger will be None
        # LoggingHandler will create a unique logger_name
        self.logging_handler = LoggingHandler(
            logger_name="folder_monitor",
            log_file_name=f"monitor_{monitor_path}_to_{destination_path}.log",
            config_file=monitor_config_path,
            config_section="folder_monitor",
        )

        self.logger = self.logging_handler.logger
        self.logger.debug(f"MonitorHandler: exiting __init__")


    def start_monitor(self):
        """Start monitoring the specified folder for changes."""
        rclone_handler = RcloneHandler(self.destination_path, self.base_path, self.sync_mode, self.logger)
        event_handler = MyEventHandler(rclone_handler, self.logger)
        self.observer = Observer()
        self.observer.schedule(event_handler, self.monitor_path, recursive=True)
        self.observer.start()
        self.logger.info(f"Observer {self.observer.name} started on folder {self.monitor_path}")

    def stop_monitor(self):
        if self.observer is not None:
            self.observer.stop()
            self.observer.join()
            self.logger.info("Monitor stopped.")
            self.observer = None

    def __del__(self):
        self.logger.debug("MonitorHandler: __del__")
        self.stop_monitor()


if __name__ == "__main__":
    print("This is file_monitor script running directly.")
    parser = argparse.ArgumentParser(description="This script monitors changes on files and subfolders in the monitor folder.")
    parser.usage = "python folder_monitor.py --destination-path <path> --base-path <path> --monitor-path <path> --sync-mode <True/False> --monitor-config-path <path>"
    parser.add_argument("--destination-path", type=str, help="The destination path, usually a folder on a remote cloud storage", required=True)
    parser.add_argument("--monitor-path", type=str, help="The path of the folder to monitor for changes", required=True)
    parser.add_argument("--base-path", type=str, help="A path or folder name. Everything after base-path is copied to the destination or deleted from the destination, Default =''", default="")
    parser.add_argument("--sync-mode", type=str, help="Allow deletion of files and folders on the destination path. Default is False", default="False")
    parser.add_argument("--monitor-config-path", type=str, help="Path of monitor configuration file. Default is ../conf/monitor.yaml", default="../conf/monitor.yaml")

    args = parser.parse_args()

    if args.destination_path is None:
        print("No destination path provided. Please provide a destination path.")
        sys.exit(1)
    if args.monitor_path is None:
        print("No monitor path provided. Please provide a monitor path.")
        sys.exit(1)

    monitor_handler = MonitorHandler(args.monitor_path, args.destination_path, args.base_path, args.sync_mode, args.monitor_config_path)
    logger = monitor_handler.logger
    monitor_handler.start_monitor()

    # Keep the script running on the main thread
    # until interrupted by the user          
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        # print("KeyboardInterrupt received. Stopping the monitor...")
        logger.info("KeyboardInterrupt received. Stopping the monitor...")
    except SystemExit:
        # print("SystemExit received. Stopping the monitor...")
        logger.info("SystemExit received. Stopping the monitor...")
    finally:
        # Stop the observer
        monitor_handler.stop_monitor()

