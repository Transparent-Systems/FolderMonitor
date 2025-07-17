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
    
    Args:
        destination_path (str): The path to the destination where the file or folder will be copied to.
        base_path (str): The base path of the source_path, used to strip the base path from the source_path.
        copy_mode (str): [copy | sync] Sync allows deletion of files and folders at the destination path.
        Examples:
            >>> rclone_handler = RcloneHandler("e2:/test-foldermonitor/Test", "Test", True)
            >>> rclone_handler.copy("D:/Test/test1.txt", False)
    """

    def __init__(self, destination_path, base_path="", copy_mode="copy", logger=None):
        self.logger = logger
        self.destination_path = destination_path.replace("\\", "/")    # Ensure forward slashes for compatibility with rclone
        self.destination_path = self.destination_path.rstrip("/") # Ensure no trailing slash
        self.base_path = base_path.replace("\\", "/") # Ensure forward slashes for compatibility with rclone   
        self.base_path = self.base_path.rstrip("/") # Ensure no trailing slash
        self.copy_mode = copy_mode.lower()
        if not(copy_mode == "copy" or copy_mode == "sync"):
            self.logger.error("Invalid value for copy_mode. Please use 'copy' or 'sync'.")
            sys.exit(1)
       


    def __get_relative_folder(self, path, token):
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


    def copy(self, source_path, is_directory=False):
        """
        Copy the file or folder to the destination path using rclone
        This implementation priorizes reliability over speed.
        It uses "rclone copy" instead of "rclone copyto"
        If a destination has a versioned file system and the fie has been deleted, then copyto will fail.
        The copy command will always work, even if the file has been deleted at the destination.
        A "rcone sync --include" command may work, but is higher risk

        Args:
            source_path (str): The path to the file or folder to be copied.

        Examples:
            >>> copy("D:/Test/test1.txt")
            >>> copy("D:/Test")
        """

        source_path = source_path.replace("\\", "/")
        # Check if the source path is a file or a directory
        if is_directory:
            source_folder = source_path
            relative_folder = self.__get_relative_folder(source_folder, self.base_path)
            destination_path = self.destination_path + relative_folder

            if self.copy_mode == 'sync':
                # Use rclone sync to ensure the destination is an exact copy of the source
                rclone_command = [rclone_path, "sync", "--transfers", "16", source_folder, destination_path]
            else:  # If copy_mode is 'copy'
                # Use rclone copy to copy the folder and its contents
                # This will not delete files at the destination that are not present in the source
                # The --transfers flag allows multiple transfers to run in parallel
                # This is useful for large folders with many files
                # The --s3-no-check-bucket flag handles the use case where the user has no CreateBucket permissions
                rclone_command = [rclone_path, "copy", "--transfers", "16", source_folder, destination_path]

            try:
                self.logger.debug(f"Running command: {' '.join(rclone_command)}")
                result_process = subprocess.run(rclone_command, capture_output=True, text=True, check=True)
                # Check if the command was successful
                if result_process.returncode == 0:
                    self.logger.debug(f"Command executed successfully: {' '.join(rclone_command)}")
                else:
                    self.logger.error(f"Error running command: {' '.join(rclone_command)}")
                    self.logger.error(f"Error details: {result_process.stderr}")
            except subprocess.CalledProcessError as e:
                self.logger.error(f"Error running command: {' '.join(rclone_command)}")
                self.logger.error(f"Error: {e}")
                self.logger.error(e.stderr)
        else:   # If the source path is a file
            relative_path = self.__get_relative_folder(source_path, self.base_path)
            destination_path = self.destination_path + relative_path
            # copyto can fail if the file has been deleted at the destination on a versioned file system
            # The --s3-no-check-bucket flag handles the use case where the user has no CreateBucket permissions 
            # If copyto fails we fall back to sync            
            rclone_command = [rclone_path, "copyto", "--transfers", "16", "--s3-no-check-bucket", source_path, destination_path]

            try:
                self.logger.debug(f"Running command: {' '.join(rclone_command)}")
                # If command fails it will trigger an exception
                result_process = subprocess.run(rclone_command, capture_output=True, text=True, check=True)
                # Check if the command was successful
                if result_process.returncode == 0:
                    self.logger.debug(f"Command executed successfully: {' '.join(rclone_command)}")
                else:
                    self.logger.error(f"Error running command: {' '.join(rclone_command)}")
                    self.logger.error(f"Error: {e}")
                    self.logger.error(e.stderr)
            except subprocess.CalledProcessError as e:
                self.logger.error(f"Error running command: {' '.join(rclone_command)}")
                self.logger.error(f"Error: {e}")
                self.logger.error(e.stderr)
                self.__process_file_with_include(source_path)

    # Delete the file or folder at the destination path using rclone
    def delete(self, source_path, is_directory=False):
        """
        If copy_mode is sync, then delete the file or folder at the destination using rclone.
        else, do nothing.

        If the source path is a file, it will delete the file at the destination path.
        If the source path is a folder, it will delete the folder at the destination path
            AND all its contents.

        Args:
            source_path (str): The path to the file or folder to be deleted.

        Examples:
            >>> delete("D:/Test/test1.txt")
            >>> delete("D:/Test")   # This will delete the folder and all its contents

        """

        if self.copy_mode == 'copy':
            return
        
        source_path = source_path.replace("\\", "/")
        relative_folder = self.__get_relative_folder(source_path, self.base_path)
        destination_path = self.destination_path + relative_folder

        if is_directory:
            rclone_command = [rclone_path, "delete", "--transfers", "16", "--rmdirs", destination_path]
        else:
            rclone_command = [rclone_path, "deletefile", "--transfers", "16", destination_path]

        try:
            self.logger.debug(f"Running command: {' '.join(rclone_command)}")
            result_process = subprocess.run(rclone_command, capture_output=True, text=True, check=True)

            # Check if the command was successful
            if result_process.returncode == 0:
                self.logger.debug(f"Command executed successfully: {' '.join(rclone_command)}")
            else:
                self.logger.error(f"Error details: {result_process.stderr}")
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Error running command: {' '.join(rclone_command)}")
            self.logger.error(f"Error: {e}")
            self.logger.error(e.stderr)
        
    def __process_file_with_include(self, source_path):
        #    Try to copy the file using rclone --include
        path_split = source_path.rsplit("/", 1)
        file_name = path_split[1]
        source_folder = path_split[0]
        relative_folder = self.__get_relative_folder(source_folder, self.base_path)
        destination_path = self.destination_path + relative_folder
        rclone_command = [rclone_path, "copy", "--transfers", "16", source_folder, destination_path, "--include", file_name]

        try:
            self.logger.debug(f"Running command: {' '.join(rclone_command)}")
            result_process = subprocess.run(rclone_command, capture_output=True, text=True, check=True)
            # Check if the command was successful
            if result_process.returncode == 0:
                self.logger.debug(f"Command executed successfully: {' '.join(rclone_command)}")
            else:
                self.logger.error(f"Error running command: {' '.join(rclone_command)}")
                self.logger.error(f"Error details: {result_process.stderr}")
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Error: {e}")
            self.logger.error(e.stderr)
