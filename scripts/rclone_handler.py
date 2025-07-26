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
import sys
import shutil

rclone_path = shutil.which("rclone")

if not rclone_path:
    print("rclone executable not found in the system's PATH.")
    sys.exit(1)


class RcloneHandler:
    """
        A class to copy or delete files and folders using rclone. 
        The Use Case is to process files from a folder monitor.
        The class has been tested with Python >= 3.10 and rclone v1.64.2.
        Rclone handler copy, delete and sync oprations always use the same root source_path and destination_path.
        That is why we only have to pass in the source_path to file or folder operations
    
    Args:
        destination_path (str): The root path to the destination where the file or folder will be copied to.
        base_path (str): The base path of the source_path. Path after base_path is appended to the destination_path.
    """

    def __init__(self, destination_path: str, base_path="", logger=None, rclone_flags=''):
        self.logger = logger
        self.destination_path = destination_path.replace("\\", "/")    # Ensure forward slashes for compatibility with rclone
        self.destination_path = self.destination_path.rstrip("/") # Ensure no trailing slash
        self.base_path = base_path.replace("\\", "/") # Ensure forward slashes for compatibility with rclone   
        self.base_path = self.base_path.rstrip("/") # Ensure no trailing slash
        # rclone_flags is comma delmited string of keys and/or values
        self.rclone_flags = rclone_flags
        # for _ in rclone_flags.split(","):
        #     self.rclone_flags.append(_.strip())
       
    def _get_relative_path(self, path, token):
        path = path.replace("\\", "/")
        # Return part after base_path
        # Or entire path if base_path not found
        try:
            index = path.index(token)
            return_path = path[index + len(token):]
        except ValueError:
            return_path = path

        # Ensure the return path starts with a slash
        if not return_path.startswith("/"):
            return_path = "/" + return_path

        return return_path

    def _copy_file_with_include(self, source_path):
        """
        Copy file using rclone copy --include
        """
        path_split = source_path.rsplit("/", 1)
        file_name = path_split[1]
        source_folder = path_split[0]
        relative_folder = self._get_relative_path(source_folder, self.base_path)
        destination_path = self.destination_path + relative_folder
        return self.run_command(["copy", source_folder, destination_path, "--include", file_name], self.rclone_flags)

    def run_command_old(self, rclone_command: list[str], additional_arguments=""):
        """
        Run rclone_command is a subprocess
        Return tupe (result_code and result_output)
        Param rclone_command: list of command parts
        Param additional_arguments: comma delimited string
        """

        # Add additional_arguments to rclone_command
        if additional_arguments and not additional_arguments.isspace():
            for _ in additional_arguments.split(","):
                rclone_command.append(_.strip())

        try:
            self.logger.debug(f"Running command: {' '.join(rclone_command)}")
            result_process = subprocess.run(rclone_command, capture_output=True, text=True, check=True)
            # Check if the command was successful
            if result_process.returncode == 0:
                self.logger.debug(f"Command executed successfully: {' '.join(rclone_command)}")
                return (result_process.returncode, result_process.stdout)
            else:
                self.logger.error(f"Error running command: {' '.join(rclone_command)}")
                self.logger.error(f"Error details: {result_process.stderr}")
                return (result_process.returncode, result_process.stderr)
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Error running command: {' '.join(rclone_command)}")
            self.logger.error(f"Error: {e}")
            self.logger.error(e.stderr)
            return (e.returncode, e.stderr)

    def run_command(self, rclone_command_parms: list[str] | str, additional_arguments=""):
        """
        Run rclone_command is a subprocess
        Return tupe (result_code and result_output)
        Param rclone_command: list or comma delimited string
        Param additional_arguments: comma delimited string
        """

        # Add rclone executable
        if isinstance(rclone_command_parms, str):
            rclone_command_string = f"{rclone_path}, {rclone_command_parms}"
            # Turn string into a list
            rclone_command = []
            for _ in rclone_command_string.split(","):
                rclone_command.append(_.strip())
        else:
            rclone_command_parms.insert(0, rclone_path)
            rclone_command = rclone_command_parms

        # Add additional_arguments to rclone_command
        if additional_arguments and not additional_arguments.isspace():
            for _ in additional_arguments.split(","):
                rclone_command.append(_.strip())

        try:
            self.logger.debug(f"Running command: {' '.join(rclone_command)}")
            result_process = subprocess.run(rclone_command, capture_output=True, text=True, check=True)
            # Check if the command was successful
            if result_process.returncode == 0:
                return (result_process.returncode, result_process.stdout.strip())
            else:
                return (result_process.returncode, result_process.stderr)
        except subprocess.CalledProcessError as e:
            # This happens in case of an rclone command failure, for example running lsf command on a file
            # self.logger.error(f"Error running command: {' '.join(rclone_command)}")
            # self.logger.error(f"Error: {e}")
            # self.logger.error(e.stderr)
            return (e.returncode, e.stderr)

    def get_rclone_version(self):
        return self.run_command("--version")
    
    def list_remotes(self):
        """
            List remotes configured
        """
        return self.run_command("listremotes")
    
    def copy_file(self, source_path):
        """
        Copy source_path to the destination path
        """

        source_path = source_path.replace("\\", "/")
        relative_path = self._get_relative_path(source_path, self.base_path)
        destination_path = self.destination_path + relative_path
        # copyto can fail if the file has been deleted at the destination on a versioned file system
        # The --s3-no-check-bucket flag handles the use case where the user has no CreateBucket permissions 
        # rclone_command = ["copyto", "--transfers", "16", "--s3-no-check-bucket", source_path, destination_path]
        # rclone_parameters = "--transfers 16", "--s3-no-check-bucket"]

        (return_value, result_output) = self.run_command(["copyto", source_path, destination_path], self.rclone_flags)

        if return_value == 0:
            return (return_value, result_output)

        # rclone copyto can fail if a file has been deleted at the destination on a versioned file system
        # If copyto fails, we try to copy the file using rclone --include
        # This is a fallback mechanism
        # Check result_output for MethodNotAllowed
        if ("MethodNotAllowed" in result_output):
            return self._copy_file_with_include(source_path)


    def copy_folder(self, source_path):
        """
        Copy the source folder to the destination path using rclone

        Args:
            source_path (str): The path to the source folder
        """

        source_path = source_path.replace("\\", "/")
        relative_folder = self._get_relative_path(source_path, self.base_path)
        destination_path = self.destination_path + relative_folder

        # Copy the folder contents
        # This will not delete files at the destination that are not present in the source
        return self.run_command(["copy", source_path, destination_path], self.rclone_flags)

    def sync_folder(self, source_path):
        """
        Sync the source folder to the destination path using rclone
        Files deleted in the source folder will be deleted at the destation path.

        Args:
            source_path (str): The path to the source folder
        """

        source_path = source_path.replace("\\", "/")
        source_folder = source_path
        relative_folder = self._get_relative_path(source_folder, self.base_path)
        destination_path = self.destination_path + relative_folder

        # Use rclone sync to ensure the destination is an exact copy of the source
        return self.run_command(["sync", source_path, destination_path], self.rclone_flags)
    

    def delete_file(self, source_path):
        """
        Delete the file at the destination using rclone.

        Args:
            source_path (str): The path to the destination file
        """

        source_path = source_path.replace("\\", "/")
        relative_folder = self._get_relative_path(source_path, self.base_path)
        destination_path = self.destination_path + relative_folder
        # We use rclone delete (instead of deletefile) as it also works when file does not exist on destination_path
        # This could happen is DirDeleteEvent is triggered before FileDeleteEvent
        # Using rclone delete reduces noise in the log
        return self.run_command(["delete", destination_path],self.rclone_flags)


    def delete_folder(self, source_path):
        """
        Delete destination folder using rclone.

        Args:
            source_path (str): The path to the destination folder to be deleted.
        """

        source_path = source_path.replace("\\", "/")
        relative_folder = self._get_relative_path(source_path, self.base_path)
        destination_path = self.destination_path + relative_folder
        # rclone delete is safer than purge
        return self.run_command(["delete", "--rmdirs", destination_path], self.rclone_flags)

       
