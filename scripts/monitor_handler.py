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
    MonitorEventHandler: Handles file system events and triggers rclone operations.
    MonitorHandler: Manages the observer and event handler lifecycle.
"""

import logging
import fnmatch
import time
import threading

from pathlib import Path
from logging.handlers import RotatingFileHandler
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from watchdog.events import (
    FileSystemEvent,
    FileClosedEvent,
    FileCreatedEvent,
    FileDeletedEvent,
    FileModifiedEvent,
    FileMovedEvent,
    DirCreatedEvent,
    DirDeletedEvent,
    DirMovedEvent,
)
from scripts.rclone_handler import RcloneHandler
from scripts.action_handler import ActionContext, ActionDispatcher, RcloneActionHandler
from scripts.utils.rclone_util import CheckPath
from scripts.utils.logging_util import get_unique_logger

def is_excluded(path_str: str, exclude_patterns: list[str]) -> bool:
    """
    Checks if a path matches any of the exclude patterns.
    """

    # Iterate over exluded patterns
    for pattern in exclude_patterns:
        # First check entire path
        path_obj = Path(path_str)
        if (fnmatch.fnmatch(path_obj, pattern)):
            return True

        # Next check path parts
        path_list = list(path_obj.parts)
        for path in path_list:
            if (fnmatch.fnmatch(path, pattern)):
                return True
    
    return False


class MonitorEventHandler(FileSystemEventHandler):
    """
    A class to handle file system events.
    It is used by the watchdog library to monitor a folder for changes.
    """

    # These are instance attributes, defined here with type hints for clarity
    # and static analysis. They will be initialized in __init__.
    action_dispatcher: ActionDispatcher
    logger: logging.Logger
    exclude_patterns: list[str]


    def __init__(
        self, action_dispatcher: ActionDispatcher, monitor_config: dict, logger: logging.Logger | None = None
    ):
        super().__init__()
        self.action_dispatcher = action_dispatcher
        self.exclude_patterns = monitor_config.get("exclude_patterns", [])
        self.logger = logger or logging.getLogger(__name__)
        self.logger.debug("MonitorEventHandler initialized")

    def on_any_event(self, event):
        """
        Catch-all event handler for any file system event.

        This method is primarily used for debugging purposes to log all
        events that occur, regardless of their type. It does not perform
        any specific actions based on the event.

        Args:
            event (FileSystemEvent): The event object representing the file system change.
        """
        self.logger.debug(f"on_any_event: Event type: {event.event_type}  Path: {event.src_path}")
        pass

    def on_created(self, event):
        """
        Handles file and directory creation events.

        For directory creation, the actual copy operation is postponed to the
        `on_modified` event, as directory creation often implies subsequent
        file additions. For file creation, the copy is also postponed to
        `on_modified` or `on_closed` for reliability with large files.

        Args:
            event (FileSystemEvent): The creation event object.
        """

        if is_excluded(event.src_path, self.exclude_patterns):
            self.logger.debug(
                f"Path excluded: src_path='{event.src_path}', event.is_directory={event.is_directory}, event_type={event.event_type}, type(event)={type(event).__name__}"
            )
            return

        # Queue the action
        context = ActionContext(
            action_type="created",
            src_path=event.src_path,
            is_directory=event.is_directory
        )
        self.action_dispatcher.queue_action(context)

        if event.is_directory:
            self.logger.debug(f"on_created: folder '{event.src_path}'; create postponed to on_modified event")
        else:
            # If the event is a file creation, we copy the specific file
            self.logger.debug(
                f"on_created: file '{event.src_path}'; create postponed to on_modified event"
            )

    def on_deleted(self, event):
        """
        Handles file and directory deletion events.
        """
        # Log the deletion event with the source path
        self.logger.debug(f"on_deleted: src_path='{event.src_path}'")

        if is_excluded(event.src_path, self.exclude_patterns):
            self.logger.debug(
                f"Path excluded: src_path='{event.src_path}', event.is_directory={event.is_directory}, event_type={event.event_type}, type(event)={type(event).__name__}"
            )
            return
            
        context = ActionContext(
            action_type="deleted",
            src_path=event.src_path,
            is_directory=event.is_directory
        )
        self.action_dispatcher.queue_action(context)

        return

    def on_modified(self, event):
        """
        Handles file modification events.
        """

        self.logger.debug(
            # Log the modification event details.
            f"on_modified: src_path='{event.src_path}', event.is_directory={event.is_directory}, event_type={event.event_type}, type(event)={type(event).__name__}"
        )

        if is_excluded(event.src_path, self.exclude_patterns):
            self.logger.debug(
                f"Path excluded: src_path='{event.src_path}', event.is_directory={event.is_directory}, event_type={event.event_type}, type(event)={type(event).__name__}"
            )
            return

        if not event.is_directory:
            context = ActionContext(
                action_type="modified",
                src_path=event.src_path,
                is_directory=event.is_directory
            )
            self.action_dispatcher.queue_action(context)

    def on_closed(self, event) -> None:
        """
        Handles FileClosedEvent
        """
        
        if is_excluded(event.src_path, self.exclude_patterns):
            self.logger.debug(
                f"Path excluded: src_path='{event.src_path}', event.is_directory={event.is_directory}, event_type={event.event_type}, type(event)={type(event).__name__}"
            )
            return

        # Check if the file still exists. It might have been deleted right after closing.
        if not Path(event.src_path).exists() or event.is_directory:
            return
        
        # Log the closed event details.
        self.logger.debug(
            f"on_closed: src_path='{event.src_path}', event.is_directory={event.is_directory}, event_type={event.event_type}, type(event)={type(event).__name__}"
        )
        
        context = ActionContext(
            action_type="closed",
            src_path=event.src_path,
            is_directory=event.is_directory
        )
        self.action_dispatcher.queue_action(context)

    def on_moved(self, event):
        """
        Handles file and directory move/rename events.
        """
        
        if is_excluded(event.src_path, self.exclude_patterns):
            self.logger.debug(
                f"Path excluded: src_path='{event.src_path}', event.is_directory={event.is_directory}, event_type={event.event_type}, type(event)={type(event).__name__}"
            )
            return

        # Log the move/rename event, showing both old and new paths.
        self.logger.debug(
            f"on_moved - renamed from {event.src_path} to {event.dest_path}"
        )

        context = ActionContext(
            action_type="moved",
            src_path=event.src_path,
            is_directory=event.is_directory,
            dest_path=event.dest_path
        )
        self.action_dispatcher.queue_action(context)


class MonitorHandler:
    """
    Manages the lifecycle of a file system observer to monitor a specified folder
    for changes and trigger rclone operations based on those changes.

    This class initializes an `Observer` from the `watchdog` library and
    associates it with a `MonitorEventHandler` instance. It handles the starting
    and stopping of the monitoring process.

    Attributes:
        monitor_config (dict): Configuration details for the specific monitor,
                               including `monitor_path`, `destination_path`, `enabled`,
                               and `rclone_flags`.
        log_config (dict): Configuration details for logging.
        monitor_enabled (bool): Indicates if the monitor is enabled.
        observer (Observer or None): The watchdog observer instance.
        logger (logging.Logger): The logger instance for this monitor.
    """

    def __init__(self, monitor_config, log_config):
        self.monitor_config = monitor_config
        self.log_config = log_config
        self.monitor_enabled = monitor_config.get("enabled")
        self.observer = None
        self.action_dispatcher = None
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

        self.rclone_flags = monitor_config.get("rclone_flags", '')
        self.exclude_patterns = monitor_config.get("exclude_patterns", [])
        self.clone_flags = monitor_config.get("rclone_flags", '')
        self.logger.debug("MonitorHandler: exiting __init__")

    def start_monitor(self):
        """
        Starts monitoring the specified folder for changes.

        Initializes an `RcloneHandler` and `MonitorEventHandler`, then schedules
        the observer to monitor the `monitor_path` recursively, filtering out
        `DirModifiedEvent` to reduce noise.
        """
        rclone_handler = RcloneHandler(
            self.destination_path, self.monitor_path, self.logger, self.rclone_flags
        )
        
        # Initialize ActionDispatcher and RcloneActionHandler
        self.rclone_action_handler = RcloneActionHandler(
            rclone_handler=rclone_handler, 
            logger=self.logger,
            debounce_delay=self.monitor_config.get("debounce_delay", 2.0)
        )
        self.action_dispatcher = ActionDispatcher(handlers=[self.rclone_action_handler], logger=self.logger)
        self.action_dispatcher.start()

        event_handler = MonitorEventHandler(
            action_dispatcher=self.action_dispatcher, 
            monitor_config=self.monitor_config, 
            logger=self.logger
        )
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
            FileClosedEvent,
            DirCreatedEvent,
            DirDeletedEvent,
            DirMovedEvent,
            # DirModifiedEvent, # <--- DO NOT INCLUDE THIS IF YOU WANT TO FILTER OUT FOLDER ACCESS CHANGES (e.g., access time changes)
            # IMPORTANT: Exclude DirModifiedEvent if you don't want folder access_time changes or other non-content
            # directory modifications to trigger on_modified. Including it can lead to excessive events.
            # If you uncomment the next line, DirModifiedEvent will be included in the events processed.
        ]

        self.observer.schedule(
            event_handler=event_handler,
            path=self.monitor_path,
            recursive=True,
            event_filter=event_types_to_monitor,
        )

        self.observer.start()
        self.logger.info(
            f"Observer {self.observer.name} started on folder {self.monitor_path}"
        )

    def stop_monitor(self):
        """
        Stops the file system observer.

        If an observer is running, it is stopped and joined, and its status is logged.
        """
        if self.observer is not None:
            self.observer.stop()
            self.observer.join()
            self.logger.info("Monitor stopped.")
            self.observer = None
        
        if self.action_dispatcher is not None:
            self.action_dispatcher.stop()
            self.action_dispatcher = None

        if hasattr(self, 'rclone_action_handler') and self.rclone_action_handler is not None:
            self.rclone_action_handler.stop()
            self.rclone_action_handler = None