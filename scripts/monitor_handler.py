"""
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

import logging
from pathlib import Path
from logging.handlers import RotatingFileHandler
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from watchdog.events import (
    FileSystemEvent,
    FileCreatedEvent,
    FileDeletedEvent,
    FileModifiedEvent,
    FileMovedEvent,
    DirCreatedEvent,
    DirDeletedEvent,
    DirMovedEvent,
    DirModifiedEvent,
    FileClosedEvent,
)
from rclone_handler import RcloneHandler
from utils.rclone_util import CheckPath
from utils.logging_util import get_unique_logger


class MyEventHandler(FileSystemEventHandler):
    """
    A class to handle file system events.
    It is used by the watchdog library to monitor a folder for changes.
    """

    # These are instance attributes, defined here with type hints for clarity
    # and static analysis. They will be initialized in __init__.
    rclone_handler: RcloneHandler
    check_path: CheckPath
    logger: logging.Logger

    def __init__(
        self, rclone_handler: RcloneHandler, logger: logging.Logger | None = None
    ):
        super().__init__()
        self.rclone_handler = rclone_handler
        self.check_path = CheckPath(rclone_handler=rclone_handler)
        self.logger = logger or logging.getLogger(__name__)
        self.logger.debug("MyEventHandler initialized")

    def on_any_event(self, event):
        """
        Catch-all event handler.
        This is useful for debugging and seeing all events that occur.
        """
        self.logger.debug(f"Event type: {event.event_type}  Path: {event.src_path}")
        pass

    def on_created(self, event):
        if event.is_directory:
            # If the event is a directory creation, we copy the entire folder
            self.logger.info(
                f"on_created: folder '{event.src_path}'; create postponed to on_modified event"
            )
        else:
            # If the event is a file creation, we copy the specific file
            self.logger.debug(
                f"on_created: file '{event.src_path}'; create postponed to on_modified event"
            )

    def on_deleted(self, event):
        self.logger.info(f"on_deleted: src_path='{event.src_path}'")

        # watchdog v6.0.0 never triggers a DirDeletedEvent. This test is just for future use.
        if event.is_directory:
            # If the event is a directory deletion, we delete the entire folder
            self.rclone_handler.purge_folder(destination_path=destination_path)
            return

        # After all files have been delete on Object Storage, all emptry folders will be gone.
        # So it is possible that the delete may fail.
        # We can test if destination directory exists in case backend type is local
        destination_path = self.rclone_handler.get_destination_path(event.src_path)

        if (
            self.rclone_handler.backend_type is None
            or self.rclone_handler.backend_type in ["ftp"]
        ):
            
            head = Path(destination_path).parent.as_posix()
            tail = Path(destination_path).name
            (found, isdir, result_output) = self.check_path.basename_exists(
                parent_path=head, base_name=tail
            )

            # If base_name is not found than return
            if not found:
                return

            if isdir:
                (return_code, return_output) = self.rclone_handler.purge_folder(
                    destination_path=destination_path
                )
            else:
                (return_code, return_output) = self.rclone_handler.delete_file(
                    destination_path=destination_path
                )
        else:
            (return_code, return_output) = self.rclone_handler.delete_file(
                destination_path=destination_path
            )

        return

    def on_modified(self, event):
        """
        Handles file modification events.
        We have filtered out DirModifiedEvent noise (like access_time changes) by checking if the path is a directory.
        So we shoud not receive DirModifiedEvent events here.
        However, a file is removed from a folder, then wathdog triggers a FileModifiedEvent on the folder of that file.
        So, we check if the path exist, if not, then skip further processing
        """

        if not Path(event.src_path).exists():
            # Watchdog triggered FileModifiedEvent event on folder
            return

        self.logger.info(
            f"on_modified: src_path='{event.src_path}', event.is_directory={event.is_directory}, event_type={event.event_type}, type(event)={type(event).__name__}"
        )
        self.rclone_handler.copy_file(source_path=event.src_path)
        return

    def on_closed(self, event) -> None:
        if not Path(event.src_path).exists():
            return

        self.logger.info(
            f"on_closed: src_path='{event.src_path}', event.is_directory={event.is_directory}, event_type={event.event_type}, type(event)={type(event).__name__}"
        )
        self.rclone_handler.copy_file(source_path=event.src_path)

    def on_moved(self, event):
        """
        Handles events where a file or folder is moved
        The old location is event.src_path
        The new location is event.dest_path
        All events are in the Observer folder
        """

        self.logger.info(
            f"on_moved - renamed from {event.src_path} to {event.dest_path}"
        )

        if event.is_directory:
            # Remove old folder from remote
            destination_path = self.rclone_handler.get_destination_path(
                path=event.src_path
            )
            self.rclone_handler.purge_folder(destination_path=destination_path)
            # Copy new folder to remote
            self.rclone_handler.copy_folder(source_path=event.dest_path)
        else:
            # Remove old file from remote
            destination_path = self.rclone_handler.get_destination_path(
                path=event.src_path
            )
            self.rclone_handler.delete_file(destination_path=destination_path)
            # Copy new file to remote
            self.rclone_handler.copy_file(source_path=event.dest_path)


class MonitorHandler:
    """
    A class to monitor a folder for changes and trigger rclone operations.
    The class has been tested with Python >= 3.10 and rclone v1.64.2.
    Args:
        monitor_config (dictionary): The monitor configuration dictionary configured in the config.yaml file
        log_config (dictionary): The logging configuration dictionary configured on the config.yaml file
    """

    def __init__(self, monitor_config, log_config):
        self.monitor_config = monitor_config
        self.log_config = log_config
        self.monitor_enabled = monitor_config.get("enabled")
        self.observer = None
        # # Create LoggingHandler instance
        self.logger = get_unique_logger(
            log_config.get("log_level", "INFO").upper()
        )  # Default to INFO if not specified)

        if monitor_config.get("enabled") is False:
            self.logger.debug("Monitor is disabled. Exiting MonitorHandler __init__")
            return

        self.monitor_path = monitor_config.get("monitor_path")
        if not self.monitor_path:
            raise ValueError("monitor_path is required in the monitor configuration.")

        # If monitor_path does not exist, then raise an error
        if not Path(self.monitor_path).exists():
            raise FileNotFoundError(
                f"Monitor path '{self.monitor_path}' does not exist. Please check the configuration."
            )

        self.destination_path = monitor_config.get("destination_path")
        if not self.destination_path:
            raise ValueError(
                "destination_path is required in the monitor configuration."
            )

        self.rclone_flags = monitor_config.get("rclone_flags", '"--transfers, 4')
        self.logger.debug("MonitorHandler: exiting __init__")

    def start_monitor(self):
        """Start monitoring the specified folder for changes."""
        rclone_handler = RcloneHandler(
            self.destination_path, self.monitor_path, self.logger, self.rclone_flags
        )
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

        self.observer.schedule(
            event_handler,
            self.monitor_path,
            recursive=True,
            event_filter=event_types_to_monitor,
        )
        # self.observer.schedule(event_handler, self.monitor_path, recursive=True)
        self.observer.start()
        self.logger.info(
            f"Observer {self.observer.name} started on folder {self.monitor_path}"
        )

    def stop_monitor(self):
        self.logger.info(f"Stopping monitor for {self.monitor_path}")
        if self.observer is not None:
            self.observer.stop()
            self.observer.join()
            self.logger.info("Monitor stopped.")
            self.observer = None