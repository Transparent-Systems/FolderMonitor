import os
import time
import sys

# Add the path to the 'scripts' directory to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from base_handler import BaseHandler

"""
This script contains utility static methods and classes for rclone
"""

class CheckPath:
    """
    Checks if a remote path exists.
    The main purpose of this class is to delay a test to allow foldermonitor to actions on the remote
    Args:
        rclone_handler (RcloneHandler): An instance of the RcloneHandler.
    """

    def __init__(self, base_handler: BaseHandler, check_delay=0):
        """
        Constructor

        Args:
            rclone_handler (RcloneHandler): An instance of the RcloneHandler.
            check_delay: optional delay timer for testing purposes only.
        """
        self.base_handler = base_handler
        self.check_delay = check_delay

    def file_exists(self, remote_path: str) -> bool:
        """
        Check if remote_path exists
        """
        time.sleep(self.check_delay)  # Sleep before checking
        return self.base_handler.file_exists(remote_path)
