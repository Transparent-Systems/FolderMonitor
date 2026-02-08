import threading
import queue
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, List
from scripts.base_handler import BaseHandler
from scripts.rclone_handler import RcloneHandler

@dataclass
class ActionContext:
    """
    Context information for an action to be handled.
    """
    action_type: str  # e.g., "created", "deleted", "modified", "moved"
    src_path: str
    is_directory: bool
    dest_path: str = None  # For moved events
    extra_data: Any = None

class ActionHandler(ABC):
    """
    Abstract base class for action handlers.
    """
    @abstractmethod
    def handle_action(self, context: ActionContext):
        pass

class DebounceManager:
    """
    Manages delayed execution of events to prevent duplicates (debouncing)
    and handle file stability waiting.
    An event is handled if:
    - The deadline is passed
    - Or the caller cancels the event and processes the event themselves.
    """
    def __init__(self, callback, logger: logging.Logger, delay: float = 2.0):
        self.callback = callback
        self.logger = logger
        self.delay = delay
        self.pending_files = {}  # Dict[str, float] -> {file_path: execute_timestamp}
        self.lock = threading.Lock()
        self.running = False
        self.thread = None

    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self._worker, daemon=True)
        self.thread.start()
        self.logger.info("DebounceManager started.")

    def stop(self):
        self.running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2)
        self.logger.info("DebounceManager stopped.")

    def add_event(self, file_path: str):
        """
        Adds a new file event with a delay deadline.
        Or updates an existing file event with a new delay deadline.
        """
        with self.lock:
            self.pending_files[file_path] = time.time() + self.delay

    def cancel_event(self, file_path: str):
        """
        Cancels a pending event for the given file path.
        """
        with self.lock:
            if file_path in self.pending_files:
                del self.pending_files[file_path]

    def _worker(self):
        while self.running:
            # Make worker wait time proportional to the delay.
            # The delay is updated when add_event is called
            time.sleep(self.delay / 10.0)
            now = time.time()
            triggered_files = []
            
            with self.lock:
                # Identify expired events
                for path, deadline in list(self.pending_files.items()):
                    if now >= deadline:
                        triggered_files.append(path)
                        del self.pending_files[path]
            
            # Process triggered events
            for path in triggered_files:
                if not self.running:
                    break
                try:
                    self.callback(path)
                except Exception as e:
                    self.logger.error(f"Error in DebounceManager callback for {path}: {e}")
            


class BaseActionHandler(ActionHandler):
    """
    Action handler that executes commands for any class that extends BaseHandler.
    """
    def __init__(self, base_handler: BaseHandler, logger: logging.Logger = None, debounce_delay: float = 1.0):
        """
        Docstring for __init__
        
        :param self: Instance of this class
        :param base_handler: An instance of a class that extends an abstract BaseHandler class, for example S3Handler or RcloneHandler.
            The purpose of this calls is to avoid code duplication. We now do not need an individual class for every type of remote handler.
        :type base_handler: BaseHandler
        :param logger: Logger
        :type logger: logging.Logger
        :param debounce_delay: The bounce delay
        :type debounce_delay: float
        """
        self.base_handler = base_handler
        self.logger = logger or logging.getLogger(__name__)
        self.debounce_manager = DebounceManager(self._execute_copy, self.logger, delay=debounce_delay)
        self.debounce_manager.start()

    def stop(self):
        self.debounce_manager.stop()

    def handle_action(self, context: ActionContext):
        try:
            if context.action_type == "created":
                self._handle_created(context)
            elif context.action_type == "deleted":
                self._handle_deleted(context)
            elif context.action_type == "modified":
                self._handle_modified(context)
            elif context.action_type == "moved":
                self._handle_moved(context)
            elif context.action_type == "closed":
                self._handle_closed(context)
        except Exception as e:
            self.logger.error(f"Error handling rclone action {context.action_type} for {context.src_path}: {e}")

    def _execute_copy(self, src_path: str):
        """
        Executes the copy operation. Used by both DebounceManager and immediate calls.
        """
        return_code, output = self.base_handler.copy_file(source_path=src_path)
        if return_code != 0:
            self.logger.warning(f"Copy failed for {src_path}. Code: {return_code}")

    def _handle_created(self, context: ActionContext):
        # In the original code, created for files was postponed to modified/closed.
        # But for directories it logged.
        pass

    def _handle_deleted(self, context: ActionContext):
        # Cancel any pending debounce for this file
        self.debounce_manager.cancel_event(context.src_path)

        remote_path = self.base_handler.get_remote_path(context.src_path)
        
        if context.is_directory:
             # watchdog typically doesn't send DirDeletedEvent but if it did:
            self.base_handler.delete_folder(remote_path=remote_path)
        else:
            self.base_handler.delete_file(remote_path=remote_path)

    def _handle_modified(self, context: ActionContext):
        if context.is_directory:
            return

        # Instead of copying immediately, add to debounce manager
        self.debounce_manager.add_event(context.src_path)

    def _handle_closed(self, context: ActionContext):
        if context.is_directory:
            return
            
        # Cancel pending debounce as we will process it now
        self.debounce_manager.cancel_event(context.src_path)

        # Execute copy immediately
        self._execute_copy(context.src_path)

    def _handle_moved(self, context: ActionContext):
        # Cancel pending debounce for the old path
        self.debounce_manager.cancel_event(context.src_path)

        if context.is_directory:
            dest_old = self.base_handler.get_remote_path(context.src_path)
            self.base_handler.delete_folder(remote_path=dest_old)
            self.base_handler.copy_folder(source_path=context.dest_path)
        else:
            dest_old = self.base_handler.get_remote_path(context.src_path)
            self.base_handler.delete_file(remote_path=dest_old)
            self.base_handler.copy_file(source_path=context.dest_path)

class RcloneActionHandler(ActionHandler):
    """
    Action handler that executes rclone commands.
    """
    def __init__(self, rclone_handler: RcloneHandler, logger: logging.Logger = None, debounce_delay: float = 1.0):
        self.rclone_handler = rclone_handler
        self.logger = logger or logging.getLogger(__name__)
        self.debounce_manager = DebounceManager(self._execute_copy, self.logger, delay=debounce_delay)
        self.debounce_manager.start()

    def stop(self):
        self.debounce_manager.stop()

    def handle_action(self, context: ActionContext):
        try:
            if context.action_type == "created":
                self._handle_created(context)
            elif context.action_type == "deleted":
                self._handle_deleted(context)
            elif context.action_type == "modified":
                self._handle_modified(context)
            elif context.action_type == "moved":
                self._handle_moved(context)
            elif context.action_type == "closed":
                self._handle_closed(context)
        except Exception as e:
            self.logger.error(f"Error handling rclone action {context.action_type} for {context.src_path}: {e}")

    def _execute_copy(self, src_path: str):
        """
        Executes the copy operation. Used by both DebounceManager and immediate calls.
        """
        return_code, output = self.rclone_handler.copy_file(source_path=src_path)
        if return_code != 0:
            self.logger.warning(f"Copy failed for {src_path}. Code: {return_code}")

    def _handle_created(self, context: ActionContext):
        # In the original code, created for files was postponed to modified/closed.
        # But for directories it logged.
        pass

    def _handle_deleted(self, context: ActionContext):
        # Cancel any pending debounce for this file
        self.debounce_manager.cancel_event(context.src_path)

        remote_path = self.rclone_handler.get_remote_path(context.src_path)
        
        if context.is_directory:
             # watchdog typically doesn't send DirDeletedEvent but if it did:
            self.rclone_handler.delete_folder(remote_path=remote_path)
        else:
            self.rclone_handler.delete_file(remote_path=remote_path)

    def _handle_modified(self, context: ActionContext):
        if context.is_directory:
            return

        # Instead of copying immediately, add to debounce manager
        self.debounce_manager.add_event(context.src_path)

    def _handle_closed(self, context: ActionContext):
        if context.is_directory:
            return
            
        # Cancel pending debounce as we will process it now
        self.debounce_manager.cancel_event(context.src_path)

        # Execute copy immediately
        self._execute_copy(context.src_path)

    def _handle_moved(self, context: ActionContext):
        # Cancel pending debounce for the old path
        self.debounce_manager.cancel_event(context.src_path)

        if context.is_directory:
            dest_old = self.rclone_handler.get_remote_path(context.src_path)
            self.rclone_handler.delete_folder(remote_path=dest_old)
            self.rclone_handler.copy_folder(source_path=context.dest_path)
        else:
            dest_old = self.rclone_handler.get_remote_path(context.src_path)
            self.rclone_handler.delete_file(remote_path=dest_old)
            self.rclone_handler.copy_file(source_path=context.dest_path)


class ActionDispatcher:
    """
    Dispatches actions to registered handlers in a separate thread.
    """
    def __init__(self, handlers: List[ActionHandler], logger: logging.Logger = None):
        self.handlers = handlers
        self.queue = queue.Queue()
        self.logger = logger or logging.getLogger(__name__)
        self.running = False
        self.thread = None

    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self._worker, daemon=True)
        self.thread.start()
        self.logger.info("ActionDispatcher started.")

    def stop(self):
        self.running = False
        self.queue.put(None) # Sentinel to unblock worker
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2)
        self.logger.info("ActionDispatcher stopped.")

    def queue_action(self, context: ActionContext):
        self.queue.put(context)

    def _worker(self):
        while self.running:
            try:
                context = self.queue.get(timeout=1)
                if context is None:
                    break
            except queue.Empty:
                continue

            for handler in self.handlers:
                try:
                    handler.handle_action(context)
                except Exception as e:
                    self.logger.error(f"Error in handler {type(handler).__name__}: {e}")
            
            self.queue.task_done()
