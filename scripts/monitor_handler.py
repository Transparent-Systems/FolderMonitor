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
from rclone_handler import RcloneHandler
from utils.rclone_util import CheckPath
from utils.logging_util import get_unique_logger


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


def is_file_stable(file_path: str, wait_time: float = 1.0) -> bool:
    """
    Checks if a file is stable by comparing its size after a short wait.
    Returns True if file size remains constant, False otherwise.
    """
    try:
        path = Path(file_path)
        if not path.exists():
            return False
        
        initial_size = path.stat().st_size
        time.sleep(wait_time)
        
        if not path.exists():
            return False
            
        final_size = path.stat().st_size
        return initial_size == final_size
    except OSError:
        return False


class RetryManager:
    """
    Manages a queue of files that failed to copy and retries them periodically.
    """
    def __init__(self, rclone_handler: RcloneHandler, logger: logging.Logger, check_interval: int = 10, expiry_time: int = 60):
        self.rclone_handler = rclone_handler
        self.logger = logger
        self.check_interval = check_interval
        self.expiry_time = expiry_time
        self.retry_queue = {}  # Dict[str, float] -> {file_path: timestamp_added}
        self.lock = threading.Lock()
        self.running = False
        self.thread = None

    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self._worker, daemon=True)
        self.thread.start()
        self.logger.info("RetryManager started.")

    def stop(self):
        self.running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2)
        self.logger.info("RetryManager stopped.")

    def add_to_queue(self, file_path: str):
        with self.lock:
            if file_path not in self.retry_queue:
                self.retry_queue[file_path] = time.time()
                self.logger.info(f"Added to retry queue: {file_path}")

    def remove_from_queue(self, file_path: str):
        with self.lock:
            if file_path in self.retry_queue:
                del self.retry_queue[file_path]
                self.logger.info(f"Removed from retry queue: {file_path}")

    def is_in_queue(self, file_path: str) -> bool:
        with self.lock:
            return file_path in self.retry_queue

    def _worker(self):
        while self.running:
            time.sleep(self.check_interval)
            
            with self.lock:
                files_to_process = list(self.retry_queue.keys())
            
            for file_path in files_to_process:
                if not self.running:
                    break

                with self.lock:
                    if file_path not in self.retry_queue:
                        continue
                    timestamp = self.retry_queue[file_path]
                
                # Check expiry
                if time.time() - timestamp > self.expiry_time:
                    self.logger.warning(f"File expired in retry queue, removing: {file_path}")
                    self.remove_from_queue(file_path)
                    continue

                # Check stability
                if not is_file_stable(file_path, wait_time=1.0):
                    self.logger.debug(f"File {file_path} is unstable (changing size). Skipping retry.")
                    continue

                # Try copy
                self.logger.debug(f"Retrying copy for: {file_path}")
                return_code, output = self.rclone_handler.copy_file(source_path=file_path)
                
                if return_code == 0:
                    self.logger.info(f"Retry success for: {file_path}")
                    self.remove_from_queue(file_path)
                else:
                    self.logger.debug(f"Retry failed for: {file_path}. Return code: {return_code}")


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
    exclude_patterns: list[str]
    retry_manager: RetryManager


    def __init__(
        self, rclone_handler: RcloneHandler, retry_manager: RetryManager, monitor_config: dict, logger: logging.Logger | None = None
    ):
        super().__init__()
        self.rclone_handler = rclone_handler
        self.retry_manager = retry_manager
        self.check_path = CheckPath(rclone_handler=rclone_handler)
        self.exclude_patterns = monitor_config.get("exclude_patterns", [])
        self.logger = logger or logging.getLogger(__name__)
        self.logger.debug("MyEventHandler initialized")

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

        if event.is_directory:
            self.logger.info(f"on_created: folder '{event.src_path}'; create postponed to on_modified event")
        else:
            # If the event is a file creation, we copy the specific file
            self.logger.debug(
                f"on_created: file '{event.src_path}'; create postponed to on_modified event"
            )

    def on_deleted(self, event):
        """
        Handles file and directory deletion events.

        When a file or directory is deleted from the monitored source path,
        this method attempts to delete the corresponding item at the destination.
        It includes specific handling for local/FTP backends to check for existence
        before deletion, and falls back to a general delete for other backend types.

        Args:
            event (FileSystemEvent): The deletion event object.
        """
        # Log the deletion event with the source path
        self.logger.info(f"on_deleted: src_path='{event.src_path}'")

        # If in retry queue, remove it so we don't keep retrying a deleted file
        if self.retry_manager.is_in_queue(event.src_path):
            self.retry_manager.remove_from_queue(event.src_path)

        if is_excluded(event.src_path, self.exclude_patterns):
            self.logger.debug(
                f"Path excluded: src_path='{event.src_path}', event.is_directory={event.is_directory}, event_type={event.event_type}, type(event)={type(event).__name__}"
            )
            return

        # watchdog v6.0.0 never triggers a DirDeletedEvent. This test is just for future use.
        # If the deleted event is a directory, purge the corresponding folder at the destination.
        # This handles cases where an entire directory is removed.
        if event.is_directory: # This code is never reached as watchdog does not trigger DirDeletedEvent
            # If the event is a directory deletion, we delete the entire folder
            destination_path = self.rclone_handler.get_destination_path(path=event.src_path)
            self.rclone_handler.delete_folder(destination_path=destination_path)
            return

        # After all files have been delete on Object Storage, all empty folders will be gone.
        # So it is possible that the delete may fail.
        # Get the corresponding destination path for the deleted item.
        destination_path = self.rclone_handler.get_destination_path(event.src_path)
        (found, isdir, result_output) = self.check_path.path_exists(path=destination_path)

        # If the base name (file or folder) is not found at the destination,
        # then:
        #   - it was already deleted
        #   - it never existed
        #   - All files in the virtual folder on object storage have been deleted
        # 
        # Nothing further to do
        if not found:
            return

        if isdir:
            (return_code, return_output) = self.rclone_handler.delete_folder(
                destination_path=destination_path
            )
        else:
            (return_code, return_output) = self.rclone_handler.delete_file(
                # If it's a file, delete the specific file.
                destination_path=destination_path
            )

        return

    def on_modified(self, event):
        """
        Handles file modification events.
        We have filtered out DirModifiedEvent noise (like access_time changes) by checking if the path is a directory.
        So we shoud not receive DirModifiedEvent events here.
        However, if a file is removed from a folder, then watchdog might trigger a FileModifiedEvent on the folder of that file.
        So, we check if the path exist, if not, then skip further processing
        """

        # If file is already in retry queue, ignore this event silently
        if self.retry_manager.is_in_queue(event.src_path):
            return

        self.logger.info(
            # Log the modification event details.
            f"on_modified: src_path='{event.src_path}', event.is_directory={event.is_directory}, event_type={event.event_type}, type(event)={type(event).__name__}"
        )

        if is_excluded(event.src_path, self.exclude_patterns):
            self.logger.debug(
                f"Path excluded: src_path='{event.src_path}', event.is_directory={event.is_directory}, event_type={event.event_type}, type(event)={type(event).__name__}"
            )
            return

        # For directories, on_modified is typically not used for copying as DirCreatedEvent handles initial creation
        # and subsequent file events handle content.
        if not event.is_directory:
            # If file is already in queue, ignore this event silently
            if self.retry_manager.is_in_queue(event.src_path):
                return
            
            # Check stability
            # Use 0.5s wait time to minimize blocking the observer thread
            if not is_file_stable(event.src_path, wait_time=0.5):
                self.logger.info(f"File {event.src_path} is unstable. Adding to retry queue.")
                self.retry_manager.add_to_queue(event.src_path)
                return
            
            # Try to copy
            return_code, output = self.rclone_handler.copy_file(source_path=event.src_path)
            if return_code != 0:
                self.logger.warning(f"Copy failed for {event.src_path}, adding to retry queue. Code: {return_code}")
                self.retry_manager.add_to_queue(event.src_path)

    def on_closed(self, event) -> None:
        """
        Handles FileClosedEvent
        Event FileClosedEvent is not triggered on Windows 11
        That's why we handle file creation in the on_modified event.
        """
        
        if is_excluded(event.src_path, self.exclude_patterns):
            self.logger.debug(
                f"Path excluded: src_path='{event.src_path}', event.is_directory={event.is_directory}, event_type={event.event_type}, type(event)={type(event).__name__}"
            )
            return

        # Check if the file still exists. It might have been deleted right after closing.
        # This is especially relevant for temporary files that are created, written, closed, and then immediately deleted.
        # Also, if the event is for a directory, we don't want to copy it here.
        if not Path(event.src_path).exists() or event.is_directory:
            return
        
        # Log the closed event details.
        self.logger.info(
            f"on_closed: src_path='{event.src_path}', event.is_directory={event.is_directory}, event_type={event.event_type}, type(event)={type(event).__name__}"
        )
        
        # If in retry queue, remove it (optimization for Linux where on_closed fires)
        if self.retry_manager.is_in_queue(event.src_path):
            self.retry_manager.remove_from_queue(event.src_path)

        # When a file is closed (finished writing), copy it to the destination.
        # This is often more reliable for large files than on_modified.
        self.rclone_handler.copy_file(source_path=event.src_path)

    def on_moved(self, event):
        """
        Handles file and directory move/rename events.

        When a file or directory is moved or renamed in the monitored source path,
        this method first deletes the item from its old location at the destination
        and then copies it to its new location at the destination.

        Args:
            event (FileMovedEvent or DirMovedEvent): The move/rename event object.
                `event.src_path` is the old path, and `event.dest_path` is the new path.
        """
        
        # If in retry queue, remove it so we don't keep retrying a moved file
        if self.retry_manager.is_in_queue(event.src_path):
            self.retry_manager.remove_from_queue(event.src_path)

        if is_excluded(event.src_path, self.exclude_patterns):
            self.logger.debug(
                f"Path excluded: src_path='{event.src_path}', event.is_directory={event.is_directory}, event_type={event.event_type}, type(event)={type(event).__name__}"
            )
            return

        # Log the move/rename event, showing both old and new paths.
        self.logger.info(
            f"on_moved - renamed from {event.src_path} to {event.dest_path}"
        )

        if event.is_directory:
            # If a directory was moved:
            # 1. Get the destination path for the old directory.
            destination_path = self.rclone_handler.get_destination_path(
                path=event.src_path
            )
            # 2. Purge (delete) the old directory from the remote.
            self.rclone_handler.delete_folder(destination_path=destination_path)
            # 3. Copy the new directory (at its new source location) to the remote.
            self.rclone_handler.copy_folder(source_path=event.dest_path)
        else:
            # If a file was moved:
            # Remove old file from remote
            destination_path = self.rclone_handler.get_destination_path(
                path=event.src_path
            )
            self.rclone_handler.delete_file(destination_path=destination_path)
            # Copy new file to remote
            self.rclone_handler.copy_file(source_path=event.dest_path)


class MonitorHandler:
    """
    Manages the lifecycle of a file system observer to monitor a specified folder
    for changes and trigger rclone operations based on those changes.

    This class initializes an `Observer` from the `watchdog` library and
    associates it with a `MyEventHandler` instance. It handles the starting
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
        self.retry_manager = None
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

        Initializes an `RcloneHandler` and `MyEventHandler`, then schedules
        the observer to monitor the `monitor_path` recursively, filtering out
        `DirModifiedEvent` to reduce noise.
        """
        rclone_handler = RcloneHandler(
            self.destination_path, self.monitor_path, self.logger, self.rclone_flags
        )
        
        # Initialize and start RetryManager
        self.retry_manager = RetryManager(rclone_handler, self.logger)
        self.retry_manager.start()

        event_handler = MyEventHandler(
            rclone_handler=rclone_handler, 
            retry_manager=self.retry_manager, 
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
        
        if self.retry_manager is not None:
            self.retry_manager.stop()
            self.retry_manager = None