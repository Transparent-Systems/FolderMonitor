import json
import logging
import uuid
import os
import shutil
import logging
import time
import sys
from pathlib import Path
import fnmatch

# Add the path to the 'scripts' directory to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from rclone_handler import RcloneHandler

"""
This script contains utility static methods and classes for rclone
"""


class CheckPath:
    """
    Checks if a specific path (file or folder) exists in a given remote path using rclone lsjson.
    Checks if a specific path (file or folder) is excluded according to excludes pattern

    Args:
        rclone_handler (RcloneHandler): An instance of the RcloneHandler.

    Returns:
        bool: True if the path is present in remote path, False otherwise.
        list: If path is present, a list of all files and folders present in remote path found so far.
            If path is not present, a list of all files and folders present in remote path.
    """

    def __init__(self, rclone_handler: RcloneHandler, check_delay=0):
        """
        Constructor

        Args:
            rclone_handler (RcloneHandler): An instance of the RcloneHandler.
            check_delay: optional delay timer for testing purposes only.
        """
        self.rclone_handler = rclone_handler
        self.check_delay = check_delay


    def is_excluded(path_str: str, exclude_patterns: list[str]) -> bool:
        """
        Checks if a path matches any of the exclude patterns.
        """

        # First check entire path
        for pattern in exclude_patterns:
            path_obj = Path(path_str)
            if (fnmatch.fnmatch(path_obj, pattern)):
                return True

            # Next check path parts
            path_list = list(path_obj.parts)
            for path in path_list:
                if (fnmatch.fnmatch(path, pattern)):
                    return True
        
        return False


    def is_excluded_v2(file_path: str, exclude_patterns: list) -> bool:
        """
        Checks if a file path matches any of the exclude patterns.
        Now handles full subpath matching like "build/app1".
        """
        path_obj = Path(file_path)
        
        # 1. Check the filename itself
        for pattern in exclude_patterns:
            # if fnmatch.fnmatch(path_obj.name, pattern):
            if fnmatch.fnmatch(path_obj.name, pattern):
                return True

        # 2. --- START OF Subpath Traversal ---
        
        # We use path_obj.parents to check all path slices efficiently. 
        # The parents iterator goes from the immediate parent up to the root.
        
        # Include the file_path itself in the check (for patterns that match the full path)
        paths_to_check = [path_obj] + list(path_obj.parents) 
        
        # We iterate over the path's ancestors and check for a relative match against patterns
        for path_to_check in paths_to_check:
            # Create a relative path string that uses forward slashes (e.g., 'build/app1')
            # We start checking from the last meaningful directory component.
            
            # NOTE: This approach assumes your patterns (e.g., 'build/app1') are relative 
            # to the project root or the current directory.
            
            # Simplified Check: Just check the string representation
            subpath_string = path_to_check.as_posix()
            normalized_subpath = f"/{subpath_string}/"
            
            for pattern in exclude_patterns:
                if '/' not in pattern and '*' not in pattern and '?' not in pattern:
                    # Look for the pattern as a whole directory name using path delimiters
                    # Example: Check if "/build/" is found in "/project/builder/app"
                    # This prevents 'build' from matching 'builder'.
                    
                    # Create the delimited pattern (e.g., "/build/" or "build/")
                    delimited_pattern = f"/{pattern}/"
                    
                    # Check if the full path string (with leading/trailing delimiters) contains the delimited pattern
                    # We must normalize the subpath_string to have leading/trailing slashes for reliable checking.
                    
                    if delimited_pattern in normalized_subpath:
                        return True

                # If the pattern is an exact match for the path slice (e.g., 'build/app1')
                if normalized_subpath.endswith(pattern) or normalized_subpath.endswith(pattern + '/'):
                    return True # Basic check for fixed path patterns

                # If the pattern is a part of the path slice (eg. /*buid*/)
                if fnmatch.fnmatch(normalized_subpath, pattern):
                        return True

        # --- END OF Subpath Traversal ---
                
        return False

    def is_excluded_v1(file_path: str, exclude_patterns: list) -> bool:
        """
        Checks if a file path matches any of the exclude patterns.
        Now handles full subpath matching like "build/app1".
        """
        path_obj = Path(file_path)
        # Ensure consistent forward slashes for matching patterns defined with '/'
        file_path_posix = path_obj.as_posix()
        
        # 1. Check the filename itself (Unchanged)
        for pattern in exclude_patterns:
            if fnmatch.fnmatch(path_obj.name, pattern):
                return True

        # --- START OF Subpath Traversal ---
        
        # We use path_obj.parents to check all path slices efficiently. 
        # The parents iterator goes from the immediate parent up to the root.
        
        # Include the file_path itself in the check (for patterns that match the full path)
        paths_to_check = [path_obj] + list(path_obj.parents) 
        
        # We iterate over the path's ancestors and check for a relative match against patterns
        for path_to_check in paths_to_check:
            # Create a relative path string that uses forward slashes (e.g., 'build/app1')
            # We start checking from the last meaningful directory component.
            
            # NOTE: This approach assumes your patterns (e.g., 'build/app1') are relative 
            # to the project root or the current directory.
            
            # Simplified Check: Just check the string representation
            subpath_string = path_to_check.as_posix()
            
            for pattern in exclude_patterns:
                
                # Use fnmatch on the full path string.
                # We check if the pattern is an explicit part of the full path string.
                if fnmatch.fnmatch(file_path_posix, '*' + pattern + '*'):
                    return True
                    
                # If the pattern is an exact match for the path slice (e.g., 'build/app1')
                if subpath_string.endswith(pattern) or subpath_string.endswith(pattern + '/'):
                    return True # Basic check for fixed path patterns

        # --- END OF Subpath Traversal ---
                
        return False


    def path_exists(
        self, path: str
    ) -> tuple[bool, bool, list]:
        """Check if path exists.

        Args:
            path (str): the path we check to exist

        Returns:
            tuple (bool, bool, list): A tuple indicating if the path exists, if it is a directory and a list of some data.
                                      The list of data can contain a list of files / folders or an error message
        """

        time.sleep(self.check_delay)  # Sleep before checking
        parent_path = Path(path).parent.as_posix()
        base_name = Path(path).name
    
        # Construct the rclone lsjson command
        rclone_command = ["lsjson", parent_path, "--max-depth", "1"]

        (result_code, result_output) = self.rclone_handler.run_command(rclone_command)

        if result_code == 0 and result_output:
            try:
                json_output = json.loads(result_output)
                found_files = []
                for item in json_output:
                    # The 'Path' field in lsjson output is relative to the queried directory.
                    # For --max-depth 1, it will usually be just the filename.
                    item_path = item.get("Path")
                    item_isdir = item.get("IsDir")
                    if item_path:
                        found_files.append(item_path)
                        # Check if item is found and is a directory
                        if item_path == base_name:
                            if item_isdir:
                                return True, True, found_files  # Directory
                            else:
                                return True, False, found_files  # File
                return False, False, found_files  # File not found in the list
            except json.JSONDecodeError:
                return (
                    False,
                    False,
                    [f"Error: Could not decode JSON output: {result_output}"],
                )
        elif result_code != 0:
            # If rclone itself returned an error (e.g., remote_path doesn't exist)
            return (
                False,
                False,
                [f"Rclone command failed when listing '{parent_path}'."],
            )
        else:
            # result_output is empty, meaning no files were found or directory is empty
            return False, False, []

    def folder_exists(self, parent_path: str, folder_name: str) -> tuple[bool, list]:
        """Check if folder exists.

        Args:
            parent_path (str): parent folder containing folder_name
            folder_name (str): the folder we check to exist

        Returns:
            tuple (bool, list): A tuple indicating if the folder exists and a list of some data.
        """

        time.sleep(self.check_delay)  # Sleep before checking

        # Construct the rclone lsjson command
        rclone_command = ["lsjson", parent_path, "--max-depth", "1"]

        (result_code, result_output) = self.rclone_handler.run_command(rclone_command)

        if result_code == 0 and result_output:
            try:
                json_output = json.loads(result_output)
                found_files = []
                for item in json_output:
                    # The 'Path' field in lsjson output is relative to the queried directory.
                    # For --max-depth 1, it will usually be just the filename.
                    item_path = item.get("Path")
                    item_isdir = item.get("IsDir")
                    if item_path:
                        found_files.append(item_path)
                        # Check if item is found and is a directory
                        if item_path == folder_name and item_isdir:
                            return True, found_files
                return False, found_files  # File not found in the list
            except json.JSONDecodeError:
                return False, [f"Error: Could not decode JSON output: {result_output}"]
        elif result_code != 0:
            # If rclone itself returned an error (e.g., remote_path doesn't exist)
            return False, [f"Rclone command failed when listing '{parent_path}'."]
        else:
            # result_output is empty, meaning no files were found or directory is empty
            return False, []

    def file_exists(self, parent_path: str, file_name: str) -> tuple[bool, list]:
        """Check if file file_name exists in folder folder_path.

        Args:
            parent_path (str): folder containing file_name
            file_name (str): the filde we check to exist

        Returns:
            tuple (bool, list): A tuple indicating if the ffile exists and a list of some data.
        """

        time.sleep(self.check_delay)  # Sleep before checking
        # Construct the rclone lsjson command
        rclone_command = ["lsjson", "--files-only", parent_path, "--max-depth", "1"]

        (result_code, result_output) = self.rclone_handler.run_command(rclone_command)

        if result_code == 0 and result_output:
            try:
                json_output = json.loads(result_output)
                found_files = []
                for item in json_output:
                    # The 'Path' field in lsjson output is relative to the queried directory.
                    # For --max-depth 1, it will usually be just the filename.
                    item_path = item.get("Path")
                    if item_path:
                        found_files.append(item_path)
                        if item_path == file_name:
                            return True, found_files
                return False, found_files  # File not found in the list
            except json.JSONDecodeError:
                return False, [f"Error: Could not decode JSON output: {result_output}"]
        elif result_code != 0:
            # If rclone itself returned an error (e.g., remote_path doesn't exist)
            return False, [f"Rclone command failed when listing '{parent_path}'."]
        else:
            # result_output is empty, meaning no files were found or directory is empty
            return False, []
