"""
rclone_handler.py
Author: John Zoetebier
Date: 2025-05-10

Description:
    This script implements the RcloneHandler class, which provides functionality
    to copy or delete files and folders using the rclone tool. The class is
    designed to handle file operations in a reliable manner, ensuring compatibility
    with versioned file systems and folder structures.

    The script uses the rclone tool to copy or delete files and folders using rclone.
    You can download rclone from https://rclone.org/downloads/

Requirements:
- rclone must be installed and available in the system's PATH.
  You can download rclone from: https://rclone.org/downloads/

Usage:
- The RcloneHandler class can be used to copy files or folders to a specified
  destination or delete them if allowed. It is particularly useful for
  automating file operations in monitored folders.
- The class has been tested with Python >= 3.10 and rclone v1.64.2.
- The class is designed to be used in conjunction with a folder monitoring script.
"""

import logging
import subprocess
import shlex
import sys
import shutil
from pathlib import Path
try:
    from scripts.base_handler import BaseHandler
except ModuleNotFoundError:
    from base_handler import BaseHandler


class RcloneHandler(BaseHandler):
    """
    A class to copy or delete files and folders using rclone.
    The class has been tested with Python >= 3.10 and rclone v1.64.2.
    Rclone handler copy, delete and sync operations always use the same root source_path and root remote_path.
    """

    rclone_path = None
    is_windows = sys.platform.startswith('win')

    @classmethod
    def get_rclone_path(cls, logger: logging.Logger) -> str:
        if RcloneHandler.rclone_path:
            return RcloneHandler.rclone_path
        
        RcloneHandler.rclone_path = shutil.which("rclone")
        if RcloneHandler.rclone_path is None:
            logger.error("rclone executable not found in the system's PATH.") 
            return ""

        # Convert RcloneHandler.rclone_path to posix string
        RcloneHandler.rclone_path = str(Path(RcloneHandler.rclone_path).as_posix())
        return RcloneHandler.rclone_path

    def __init__(
        self,
        logger: logging.Logger,
        base_source_path: str,
        base_remote_path: str,
        profile_name: str
    ):
        """
        Docstring for __init__
        
        :param self: Instance of this class
        :param logger: logger instance
        :param base_source_path: Source path to copy from
        :param base_remote_path: remote path to copy to. This path is without the profile name commonly used in rclone.
        :profile_name: The profile name used in Rclone commands in format profile_name:remote_path
        """    
        self.logger = logger

        # Get rclone_path
        self.rclone_path = RcloneHandler.get_rclone_path(logger=logger)

        if (profile_name is None):
            self.profile_name = ""
        else:
            self.profile_name = profile_name

        if self.profile_name != "":
            # Check if remote_path is in the conventinal rclone format with remote_profile prefix (remote_profile:)
            remote_path_str = str(Path(base_remote_path).as_posix())
            if not remote_path_str.startswith(profile_name + ":"):
                base_remote_path = profile_name + ":" + base_remote_path

        self.base_remote_path = Path(base_remote_path)
        self.base_source_path = Path(base_source_path)

        return

    def run_command(
        self, rclone_parms: list[str], additional_args_str: str = ""
        )-> tuple[int, str ]:
        """
        Run rclone_command is a subprocess
        Return tuple (result_code and result_output)
        Param rclone_parms: list of commands
        Param additional_args_str: a string with arguments
        """

        if self.rclone_path is None:
            self.logger.error("rclone executable not found in the system's PATH.")
            return (1, "rclone executable not found in the system's PATH.")

        try:
            # Parse Additional Arguments Safely
            extra_args_list = shlex.split(additional_args_str, posix=not RcloneHandler.is_windows)
        except ValueError as e:
            self.logger.error(f"Error parsing arguments: {e}")
            return (1, f"Error parsing arguments: {e}")
        
        # Add rclone executable
        rclone_command = rclone_parms.copy()
        rclone_command.insert(0, RcloneHandler.get_rclone_path(logger=self.logger))
        # Add extra_args_list to rclone_command
        for _ in extra_args_list:
            rclone_command.append(_)

        try:
            self.logger.debug(f"Running command: {' '.join(rclone_command)}")
            result_process = subprocess.run(
                rclone_command, 
                capture_output=True,
                text=True, 
                check=True
            )

            return (result_process.returncode, result_process.stdout.strip())
        except subprocess.CalledProcessError as e:
            # This happens in case of an rclone command failure, for example running lsf command on a file
            self.logger.error(f"Error running command: {' '.join(rclone_command)}")
            self.logger.error(f"Error returncode: {e.returncode}")
            self.logger.debug(f"Error stdout: {e.stdout}")
            self.logger.debug(
                f"Error stderr: {e.stderr}"  )
            return (e.returncode, e.stderr)

    def get_remote_path(self, source_path: str) -> str:
        """
        Derives remote path from base source path and this source_path
        """

        source_path_obj = Path(source_path)
        relative_path = source_path_obj.relative_to(self.base_source_path)
        remote_path = self.base_remote_path / relative_path
        return remote_path.as_posix()

    def get_rclone_version(self):
        return self.run_command(["--version"])

    def list_remotes(self):
        """
        List remotes configured
        """
        return self.run_command(["listremotes"])

    def file_exists(self, remote_path: str) -> tuple[int, str]:
        """
        Docstring for file_exists
        
        :param self: Instance of this class
        :param remote_path: Remote path to check for existence
        :type remote_path: str
        """
        (return_value, result_output) = self.run_command(
            ["ls", remote_path]
            )

        return (return_value, result_output)

    def copy_file(self, source_path, remote_path=None) -> tuple[int, str]:
        """
        Copy source_path to remote_path.
        If remote_path is None, the remote_path is derived from the source_path
        Returns:
            (result_code, result_output)
        """

        if remote_path is None:
            remote_path = self.get_remote_path(source_path=source_path)

        # copyto can fail if the file has been deleted at the destination on a versioned file system
        (return_value, result_output) = self.run_command(
            ["copyto", source_path, remote_path]
        )

        if return_value == 0:
            return (return_value, result_output)
        else:
            # rclone copyto can fail if a file has been deleted at the destination on a versioned file system
            # If copyto fails, we try to copy the file using rclone --include
            # This is a fallback mechanism
            # Check result_output for MethodNotAllowed
            if "MethodNotAllowed" in result_output:
                source_path_obj = Path(source_path)
                file_name = source_path_obj.name
                source_folder = source_path_obj.parent
                destination_folder = self.get_remote_path(source_path=str(source_folder))
                return self.run_command(
                    [
                        "copy",
                        str(source_folder),
                        destination_folder,
                        "--include",
                        file_name,
                    ]
                )
            else:
                # Log copy_file failed
                self.logger.warning(f"copy_file failed; ; return_value={return_value}")
                return (return_value, result_output)

    def copy_folder(self, source_path):
        """
        Copy the source path to the derived destination path
        """

        remote_path = self.get_remote_path(source_path=source_path)

        # Copy the folder contents
        # This will not delete files at the destination that are not present in the source
        return self.run_command(
            ["copy", source_path, remote_path]
        )
    
    def delete_file(self, remote_path):
        """
        Delete file at remote_path
        """

        # We use rclone delete (instead of deletefile) as it also works when file does not exist on remote_path
        # This could happen is DirDeleteEvent is triggered before FileDeleteEvent
        # Using rclone delete reduces noise in the log
        return self.run_command(["delete", remote_path])

    def delete_folder(self, remote_path):
        """
        Delete contents inside remote_path
        """

        return self.run_command(
            ["delete", "--rmdirs", remote_path]
        )

