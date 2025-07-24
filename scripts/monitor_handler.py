"""
Script: monitor_handler.py
Version: v1.0.0
Author: John Zoetebier
Date: 2025-05-10
    Monitors a folder for changes and handles events for files and folders
    The script utilizes the rclone_handler module to copy or delete files and folders using rclone.
    The script is compatible with both Windows and Linux systems.
Requirements:
    1) rclone v1.64.2 (https://rclone.org/downloads/)
    2) Python 3.13.0 (https://www.python.org/downloads/)
    3) Python modules in requirements.txt
Classes:
    MyEventHandler: Handles file system events and triggers rclone operations.
    MonitorHandler: Manages the observer and event handler lifecycle.
"""

import os
import logging
import uuid

import utils
from logging.handlers import RotatingFileHandler
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from watchdog.events import FileSystemEvent, FileCreatedEvent, FileDeletedEvent, FileModifiedEvent, FileMovedEvent, DirCreatedEvent, DirDeletedEvent, DirMovedEvent, DirModifiedEvent, FileClosedEvent
from rclone_handler import RcloneHandler


# def get_unique_logger(log_level = "INFO"):
#     """
#     # Create a unique logger instance with a name based on UUID import uuid
#     """
#     # Get globally unique logger name
#     logger_name = f"Logger_{uuid.uuid4()}"
#     logger = logging.getLogger(logger_name)
    
#     # Set the logger to debug level initially for its internal setup messages.
#     # The effective level will also be governed by the root logger's level.
#     level_map = {
#         "DEBUG": logging.DEBUG,
#         "INFO": logging.INFO,
#         "WARNING": logging.WARNING,
#         "ERROR": logging.ERROR,
#         "CRITICAL": logging.CRITICAL
#     }
#     logger.setLevel(level_map.get(log_level, logging.NOTSET)) # Use .get with default for robustness
#     return logger


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
        super().__init__()
        self.rclone_handler = rclone_handler
        self.logger = logger if logger else logging.getLogger(__name__)
        self.logger.debug("MyEventHandler initialized")
       
    def on_created(self, event):
        if event.is_directory:
            # If the event is a directory creation, we copy the entire folder
            self.logger.info(f"on_created: folder '{event.src_path}'; create postponed to on_modified event")
        else:
            # If the event is a file creation, we copy the specific file
            self.logger.debug(f"on_created: file '{event.src_path}'; create postponed to on_modified event")


    def on_deleted(self, event):
        self.logger.info(f"on_deleted: src_path='{event.src_path}'") 
        if event.is_directory:
            # If the event is a directory deletion, we delete the entire folder
            # This may never happen as watchdog does trigger a FileDeletedEvent for directories
            self.rclone_handler.delete_folder(event.src_path)
        else:
            # If the event is a file deletion, we delete the specific file
            (return_code, return_output)  = self.rclone_handler.delete_file(event.src_path)
            # Watchdog can trigger a FileDeletedEvent for a directory if its contents change,
            # so we log the return code for debugging purposes
            # If the return code is 0, the file was successfully deleted
            if return_code == 0:
                return
            
            # watchdog can trigger a FileDeletedEvent for a directory if the directory is deleted
            # so we log the return code for debugging purposes
            self.logger.debug(f"on_deleted: failed to delete {event.src_path}, return code: {return_code}")
            # Watchdog trigger FileDeletedEvent for deleted folder, so delete folder here.
            self.logger.debug(f"on_deleted: delete folder '{event.src_path}'")
            self.rclone_handler.delete_folder(event.src_path)


    def on_modified(self, event):
        """
        Handles file modification events.
        We have filtered out DirModifiedEvent noise (like access_time changes) by checking if the path is a directory.
        So we shoud not receive DirModifiedEvent events here.
        However, a file is removed from a folder, then wathdog triggers a FileModifiedEvent on the folder of that file.
        So, we check if the path exist, if not, then skip further processing
        """

        if not os.path.exists(event.src_path):
            # Watchdog triggered FileModifiedEvent event on folder
            return

        self.logger.info(f"on_modified: src_path='{event.src_path}', event.is_directory={event.is_directory}, event_type={event.event_type}, type(event)={type(event).__name__}")
        self.rclone_handler.copy_file(event.src_path)

    def on_closed(self, event) -> None:
        if not os.path.exists(event.src_path):
            return

        self.logger.info(f"on_closed: src_path='{event.src_path}', event.is_directory={event.is_directory}, event_type={event.event_type}, type(event)={type(event).__name__}")
        self.rclone_handler.copy_file(event.src_path)


    def on_moved(self, event):
        self.logger.info(f"on_moved - renamed from {event.src_path} to {event.dest_path}")

        if event.is_directory:
            # Remove src_path (old folder) from remote
            self.rclone_handler.delete_folder(event.src_path)
            # Copy dest_path (new folder) to remote
            self.rclone_handler.copy_folder(event.dest_path)
        else:
            # Remove src_path (old file) from remote
            self.rclone_handler.delete_file(event.src_path)
            # Copy dest_path (new file) to remote
            self.rclone_handler.copy_file(event.dest_path)

    def __del__(self):
        self.logger.debug("Event handler closed")
        self.rclone_handler = None


class MonitorHandler:
    """
    A class to monitor a folder for changes and trigger rclone operations.  
    The class has been tested with Python >= 3.10 and rclone v1.64.2.
    Args:
        monitor_config (dictionary): The monitor configuration dictionary configured in the monitor yaml file
        log_config (dictionary): The logging configuration dictionary configured on the monitor yaml file
    """
    def __init__(self, monitor_config, log_config):
        self.monitor_config = monitor_config
        self.log_config = log_config
        self.monitor_enabled = monitor_config.get("enabled")        
        self.observer = None
        # # Create LoggingHandler instance
        self.logger = utils.get_unique_logger(log_config.get('log_level', 'INFO').upper()) # Default to INFO if not specified)

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
        self.copy_mode = monitor_config.get('copy_mode', 'sync')  # Default to 'sync' if not specified
        self.rclone_flags = monitor_config.get('rclone_flags', '"--transfers, 4, --s3-no-check-bucket') 
        self.logger.debug("MonitorHandler: exiting __init__")


    def start_monitor(self):
        """Start monitoring the specified folder for changes."""
        rclone_handler = RcloneHandler(self.destination_path, self.base_path, self.logger, self.rclone_flags)
        event_handler = MyEventHandler(rclone_handler, self.logger)
        self.observer = Observer()

        # Define the event filter:
        # Include all event types except DirModifiedEvent.
        # This means on_modified will only be called for FileModifiedEvent.
        # on_created, on_deleted, on_moved will still work for both files and directories.
        event_types_to_monitor = [
            FileCreatedEvent,
            FileDeletedEvent,
            FileModifiedEvent,
            FileMovedEvent,
            DirCreatedEvent,
            DirDeletedEvent,
            DirMovedEvent,
            # DirModifiedEvent, # <--- DO NOT INCLUDE THIS IF YOU WANT TO FILTER OUT FOLDER ACCESS CHANGES
            # IMPORTANT: Exclude DirModifiedEvent if you don't want folder access_time changes
            # or other non-content directory modifications to trigger on_modified.
            # If you uncomment the next line, DirModifiedEvent will be included.
            # DirModifiedEvent, # <--- DO NOT INCLUDE THIS IF YOU WANT TO FILTER OUT FOLDER ACCESS CHANGES
        ]

        self.observer.schedule(event_handler, self.monitor_path, recursive=True, event_filter=event_types_to_monitor)
        # self.observer.schedule(event_handler, self.monitor_path, recursive=True)
        self.observer.start()
        self.logger.info(f"Observer {self.observer.name} started on folder {self.monitor_path}")

    def stop_monitor(self):
        self.logger.info(f"Stopping monitor for {self.monitor_path}")
        if self.observer is not None:
            self.observer.stop()
            self.observer.join()
            self.logger.info("Monitor stopped.")
            self.observer = None

    
