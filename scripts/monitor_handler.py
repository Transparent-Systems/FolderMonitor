"""
Script: folder_monitor.py
Version: v2.0.0
Author: John Zoetebier
Date: 2025-05-10
    Monitors a folder for changes and handles events for files and folders
    The script utilizes the rclone_handler module to copy or delete files and folders using rclone.
    The script is compatible with both Windows and Linux systems.
Requirements:
    1) [rclone v1.64.2] (https://rclone.org/downloads/)
        Only required for non S3 remotes
    2) Python 3.13.0 (https://www.python.org/downloads/)
    3) Python modules in requirements.txt
Classes:
    MonitorEventHandler: Handles file system events and triggers remote operations.
    MonitorHandler: Manages the observer and event handler lifecycle.
"""

import logging
import fnmatch
import time
import threading

from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from watchdog.events import (
    FileClosedEvent,
    FileCreatedEvent,
    FileDeletedEvent,
    FileModifiedEvent,
    FileMovedEvent,
    DirCreatedEvent,
    DirDeletedEvent,
    DirMovedEvent,
)
from scripts.action_handler import ActionContext, ActionDispatcher, BaseActionHandler
from scripts.profile_handler import ProfileHandler
from scripts.utils.logging_util import get_unique_logger
from scripts.base_handler_factory import BaseHandlerFactory

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
        self.event_time: dict[str, float] = {}  # Dictionary to store event times
        self.event_time_lock = threading.Lock()
        self.stop_event = threading.Event()
        self.cleanup_thread = threading.Thread(target=self._cleanup_worker, daemon=True)
        self.cleanup_thread.start()
        self.logger.debug("MonitorEventHandler initialized")

    def stop(self):
        """Stops the cleanup worker thread."""
        self.stop_event.set()
        if self.cleanup_thread.is_alive():
            self.cleanup_thread.join(timeout=2)

    def _cleanup_worker(self):
        """Periodically removes event times older than 1 minute."""
        while not self.stop_event.is_set():
            # wait() returns True if the flag is set (stop requested),
            # and False if the timeout expires (time to run cleanup).
            if self.stop_event.wait(60):
                break
            
            now = time.time()
            cutoff = now - 60
            
            with self.event_time_lock:
                keys_to_remove = [k for k, v in self.event_time.items() if v < cutoff]
                for k in keys_to_remove:
                    self.logger.debug(f"Removing event time for {k}")
                    del self.event_time[k]

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
        Handles FileModifiedEvent events.
        """

        now = time.time()
        with self.event_time_lock:
            if event.src_path in self.event_time:
                time_diff = now - self.event_time[event.src_path]
            else:
                time_diff = 0
            self.event_time[event.src_path] = now
        # Convert now into hh:mm:ss
        time_diff_ms = int(time_diff * 1000)    # Convert to milliseconds
        
        self.logger.debug(
            # Log the modification event details.
            f"on_modified: time_diff_ms={time_diff_ms} ,  src_path='{event.src_path}', event.is_directory={event.is_directory}, event_type={event.event_type}"
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
    for changes and trigger remote operations based on those changes.

    This class initializes an `Observer` from the `watchdog` library and
    associates it with a `MonitorEventHandler` instance. It handles the starting
    and stopping of the monitoring process.
    """

    def __init__(self, monitor_config, log_config):
        self.debounce_delay = 1.0
        self.monitor_config = monitor_config
        self.log_config = log_config
        self.observer = None
        self.action_dispatcher = None
        self.event_handler = None
        # # Create LoggingHandler instance
        self.logger = get_unique_logger(
            log_config.get("log_level", "INFO").upper()
        )  # Default to INFO if not specified)

        self.monitor_path = monitor_config.get("monitor_path")
        if not self.monitor_path:
            raise ValueError("monitor_path is required in the monitor configuration.")

        # If monitor_path does not exist, then raise an error
        if not Path(self.monitor_path).exists():
            raise FileNotFoundError(
                f"Monitor path '{self.monitor_path}' does not exist. Please check the configuration."
            )

        if (monitor_config.get("remote_path") is None):
            # This is a local path, currently handled y rclone
            # Make remote_path empty string
            self.remote_path = ""
        else:
            self.remote_path = monitor_config.get("remote_path")

        self.remote_profiles = monitor_config.get("remote_profiles")
        self.exclude_patterns = monitor_config.get("exclude_patterns", [])
        self.profile_handlers: dict[str, ProfileHandler] = {}
        profile_names = ["foldermonitor", "rclone"]
        for profile_name in profile_names:
            profile_handler = ProfileHandler(
                logger=self.logger,
                app_name=profile_name
            )

            self.profile_handlers[profile_name] = profile_handler

        self.logger.debug("MonitorHandler: exiting __init__")

    def start_monitor(self):
        """
        Starts monitoring the specified folder for changes.

        Initializes an `RcloneHandler` and `MonitorEventHandler`, then schedule
        the observer to monitor the `monitor_path` recursively, filtering out
        `DirModifiedEvent` to reduce noise.
        """

        remote_profiles = self.monitor_config.get("remote_profiles")
        # Iterate over remote_profiles
        action_handlers = []
        for remote_profile in remote_profiles:
            # Instantiating a remote handler is now handled by BaseHandlerFactory
            base_handler = BaseHandlerFactory.get_handler(
                logger=self.logger,
                source_path=self.monitor_path,
                remote_path=self.remote_path,
                remote_profile=remote_profile
            )

            if (base_handler is None):
                # Log error and continuue
                self.logger.error(f"Remote profile {remote_profile} not present in either foldermonitor or rclone configuration")
                continue

            # Wrap base_handler in an instance of BaseActionHandler
            base_action_handler = BaseActionHandler(
                base_handler=base_handler,
                logger=self.logger
            )
            action_handlers.append(base_action_handler)

        self.action_dispatcher = ActionDispatcher(handlers=action_handlers, logger=self.logger)
        self.action_dispatcher.start()
        self.event_handler = MonitorEventHandler(
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
            event_handler=self.event_handler,
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

        if self.event_handler is not None:
            self.event_handler.stop()
            self.event_handler = None
        
        if self.action_dispatcher is not None:
            self.action_dispatcher.stop()
            self.action_dispatcher = None

        if hasattr(self, 'rclone_action_handler') and self.rclone_action_handler is not None:
            self.rclone_action_handler.stop()
            self.rclone_action_handler = None