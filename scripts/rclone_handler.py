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

import json
import logging
import subprocess
import shlex
import sys
import os
import shutil
from pathlib import Path

_rclone_path = shutil.which("rclone")
_is_windows = sys.platform.startswith('win')

if not _rclone_path:
    print("rclone executable not found in the system's PATH.")
    sys.exit(1)


class RcloneHandler:
    """
    A class to copy or delete files and folders using rclone.
    The class has been tested with Python >= 3.10 and rclone v1.64.2.
    Rclone handler copy, delete and sync oprations always use the same root source_path and root destination_path.
    """

    _rclone_config_json = None

    @classmethod
    def _load_rclone_config(cls, logger: logging.Logger) -> dict:
        """A class method to handle the loading of the rclone configuration."""
        if cls._rclone_config_json is None:
            print("Loading rclone config...")

            try:
                rclone_command = [_rclone_path, "config", "dump"]
                logger.debug(f"Running command: {' '.join(rclone_command)}")
                result_process = subprocess.run(
                    rclone_command, capture_output=True, text=True, check=True
                )
                # Check if the command was successful

                if result_process.returncode == 00:
                    config_data = result_process.stdout.strip()
                else:
                    config_data = {}
            except subprocess.CalledProcessError as e:
                logger.error(e.stderr)
                logger.error("Error: rclone config not found.")
                config_data = {}

            json_output = json.loads(config_data)
            cls._rclone_config_json = json_output

        return cls._rclone_config_json

    def __init__(
        self,
        base_destination_path: str,
        base_source_path: str,
        logger: logging.Logger,
        rclone_flags: str,
    ):
        """
        destination_path    : base destination path
        source_path         : base source path
        logger              : logger instance
        rclone_flags        : comma delimited string of rclone flags
        """
        self.logger = logger
        self.base_destination_path = Path(base_destination_path)
        self.base_source_path = Path(base_source_path)
        self.rclone_flags = rclone_flags
        # Call class method to get rclone config in json format
        self.rclone_config = self._load_rclone_config(logger)
        # Derive backend name from base_destination_path
        backend_name = base_destination_path.split(":")[0]
        backend_config = self.rclone_config.get(backend_name)
        # store type as instance variable
        if backend_config is None:
            self.backend_type = None
        else:
            self.backend_type = backend_config.get("type")

        return

    def run_command(
        self, rclone_parms: list[str], additional_args_str=""
    )-> tuple[int, str ]:
        """
        Run rclone_command is a subprocess
        Return tuple (result_code and result_output)
        Param rclone_parms: list of commands
        Param additional_args_str: a string with arguments
        """

        # Parse Additional Arguments Safely
        try:
            # posix=True (default) treats backslash '\' as an escape character.
            # posix=False treats '\' as a normal character (better for Windows paths).
            extra_args_list = shlex.split(additional_args_str, posix=not _is_windows)
        except ValueError as e:
            self.logger.error(f"Error parsing arguments: {e}")
            return None
      

        # Add rclone executable
        rclone_command = rclone_parms.copy()
        rclone_command.insert(0, _rclone_path)
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

    def get_destination_path(self, path: str) -> str:
        """
        Derives path relative to source_path and suffixes it to destination path
        """

        source_path_obj = Path(path)
        relative_path = source_path_obj.relative_to(self.base_source_path)
        destination_path = self.base_destination_path / relative_path
        return destination_path.as_posix()

    def get_rclone_version(self):
        return self.run_command(["--version"])

    def list_remotes(self):
        """
        List remotes configured
        """
        return self.run_command(["listremotes"])

    def copy_file(self, source_path) -> tuple[int, list[str]]:
        """
        Copy source_path to the derived destination path
        """

        destination_path = self.get_destination_path(path=source_path)
        # copyto can fail if the file has been deleted at the destination on a versioned file system
        # The --s3-no-check-bucket flag handles the use case where the user has no CreateBucket permissions
        # rclone_command = ["copyto", "--transfers", "16", "--s3-no-check-bucket", source_path, destination_path]

        (return_value, result_output) = self.run_command(
            ["copyto", source_path, destination_path], self.rclone_flags
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
                destination_folder = self.get_destination_path(path=str(source_folder))
                return self.run_command(
                    [
                        "copy",
                        str(source_folder),
                        destination_folder,
                        "--include",
                        file_name,
                    ],
                    self.rclone_flags,
                )
            else:
                # Log copy_file failed
                self.logger.warning(f"copy_file failed; ; return_value={return_value}")
                return (return_value, result_output)

    def copy_folder(self, source_path):
        """
        Copy the source path to the derived destination path
        """

        destination_path = self.get_destination_path(path=source_path)

        # Copy the folder contents
        # This will not delete files at the destination that are not present in the source
        return self.run_command(
            ["copy", source_path, destination_path], self.rclone_flags
        )
    
    def delete_file(self, destination_path):
        """
        Delete file at destination_path
        """

        # We use rclone delete (instead of deletefile) as it also works when file does not exist on destination_path
        # This could happen is DirDeleteEvent is triggered before FileDeleteEvent
        # Using rclone delete reduces noise in the log
        return self.run_command(["delete", destination_path], self.rclone_flags)

    def delete_folder(self, destination_path):
        """
        Delete contents inside destination_path
        """

        return self.run_command(
            ["delete", "--rmdirs", destination_path], self.rclone_flags
        )

    def purge_folder(self, destination_path):
        """
        Delete content and all file versions inside destination_path. 
        Purge will also remove the folder at destination_path
        Important: 
            This method will remove all versions on a versioned storage backend.
        """

        return self.run_command(["purge", destination_path], self.rclone_flags)
    
