import logging
import threading
import time
from scripts.base_handler_factory import BaseHandlerFactory
from scripts.utils.generic_util import convert_to_seconds


class BackupHandler():
    """
    Executes backup operations for a given monitor configuration.

    This class handles both one-off and recurring backups based on the
    'interval' setting in the monitor's backup configuration.
    """

    def __init__(self, logger, monitor_config):
        self.logger = logger or logging.getLogger(__name__)
        self.monitor_config = monitor_config
        self.monitor_name = monitor_config.get("name")
        self.backup_thread = None
        self.stop_event = threading.Event()

    def stop(self):
        """
        Stops the backup task.
        """
        self.stop_event.set()
        if self.backup_thread and self.backup_thread.is_alive():
            self.backup_thread.join(timeout=2)

    def start(self):
        """
        Starts the backup task.
        """
        self.stop_event.clear()
        self.backup_thread = threading.Thread(target=self._run_loop, daemon=True, name=f"Backup-{self.monitor_name}")
        self.backup_thread.start()
        return self.backup_thread

    def _perform_backup(self, reason="scheduled"):
        """
        Perform a backup for the given monitor configuration.
        """
        monitor_name = self.monitor_config["name"]
        monitor_path = self.monitor_config["monitor_path"]
        remote_path = self.monitor_config["remote_path"]
        
        self.logger.debug(
            f"Performing {reason} backup for monitor [{monitor_name}] at {time.ctime()} for: {monitor_path} -> {remote_path}"
        )

        remote_profiles = self.monitor_config.get("remote_profiles", [""])
        if not remote_profiles:
            remote_profiles = [""]

        # Iterate over remote_profiles
        for remote_profile in remote_profiles:
            try:
                handler = BaseHandlerFactory.get_handler(
                    logger=self.logger,
                    source_path=monitor_path,
                    remote_path=remote_path,
                    profile_type=remote_profile
                )

                if handler:
                    self.logger.debug(f"[{monitor_name}] Starting folder copy...")
                    handler.copy_folder(source_path=monitor_path)
                    self.logger.debug(f"[{monitor_name}] Finished folder copy.")
                else:
                    self.logger.error(f"[{monitor_name}] Could not instantiate handler for backup.")
            except Exception as e:
                self.logger.error(f"[{monitor_name}] Backup failed: {e}")

    def _run_loop(self):
        """
        The main loop for the backup task.
        """
        backup_config = self.monitor_config.get("backup", {})
        if not backup_config:
            self.logger.debug(f"Backup for monitor '{self.monitor_name}' not configured. Backup is disabled.")
            return

        raw_interval = backup_config.get("interval", "0")
        interval_seconds = convert_to_seconds(raw_interval)
        self.logger.debug(f"[{self.monitor_name}] Backup interval is {interval_seconds} seconds")

        if interval_seconds == 0:
            self.logger.debug(f"[{self.monitor_name}] Performing one-off backup.")
            self._perform_backup(reason="one-off (interval 0)")
            return

        # Initial backup before loop
        self.logger.debug(f"[{self.monitor_name}] Performing initial backup.")
        self._perform_backup(reason="initial backup")

        self.logger.debug(f"[{self.monitor_name}] Backup scheduled every {interval_seconds} seconds.")
        while not self.stop_event.is_set():
            # Wait for interval OR stop event
            if self.stop_event.wait(interval_seconds):
                break
            self._perform_backup(reason="scheduled")