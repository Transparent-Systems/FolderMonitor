"""
Script: folder_copy.py
Version: v1.0.0
Author: John Zoetebier
Date: 2025-06-15
    The main purpose of folder_copy.py is to test a line in monitor_entries.txt file.
    This will show if the line has the proper parameter keys and values.
    The script is compatible with both Windows and Linux systems.
Requirements:
    1) rclone v1.64.2 (https://rclone.org/downloads/)
    2) Python 3.13.0 (https://www.python.org/downloads/)
    3) Python modules in requirements.txt
Usage:
    Example:
        python folder_copy.py --monitor-path "D:/Test/FolderMonitor" --base-path "Test" --destination-path "e2:test-zoetebier-net/Test" --sync-mode "True"

    Arguments:
        --monitor-path:        Path to the folder to monitor for changes.
        --base-path:           The path in monitor-path after base-path is appended to the destination-path. Default is ''.
        --destination-path:    Destination path, usually a folder on remote cloud storage.
        --sync-mode:           Allow deletion of files and folders on the destination path. Default is False.
        --monitor-config-path: Path to monitor configuration file. Default path is ../conf/monitor.yaml.
Notes:
    - Ensure you have the necessary permissions to access the monitored folder.
    - It is recommended to use a virtual Python environment to avoid conflicts with other packages.
    - To create and activate a virtual environment:
        python -m venv .venv
        .\\.venv\\Scripts\\Activate.ps1  (Windows)
        source .venv/bin/activate  (macOS/Linux)
    - After Python has been installed you can install required modules with:
        pip install -r requirements.txt
Entry Point:
    Parses command-line arguments, initializes logging and reclone_handler.
"""

import sys
import argparse

from logging_handler import LoggingHandler
from rclone_handler import RcloneHandler


if __name__ == "__main__":
    print("Running script file_copy.py.")
    parser = argparse.ArgumentParser(description="This script monitors changes on files and subfolders in the monitor folder.")
    parser.usage = "python folder_copy.py --destination-path <path> --base-path <path> --monitor-path <path> --sync-mode <True/False> --monitor-config-path <path>"
    parser.add_argument("--destination-path", type=str, help="The destination path, usually a folder on a remote cloud storage", required=True)
    parser.add_argument("--monitor-path", type=str, help="The path of the folder to monitor for changes", required=True)
    parser.add_argument("--base-path", type=str, help="A path or folder name. Everything after base-path is copied to the destination or deleted from the destination, Default =''", default="")
    parser.add_argument("--sync-mode", type=str, help="Allow deletion of files and folders on the destination path. Default is False", default="False")
    parser.add_argument("--monitor-config-path", type=str, help="Path of monitor configuration file. Default is ../conf/monitor.yaml", default="../conf/monitor.yaml")

    args = parser.parse_args()

    if args.destination_path is None:
        print("No destination path provided. Please provide a destination path.")
        sys.exit(1)
    if args.monitor_path is None:
        print("No monitor path provided. Please provide a monitor path.")
        sys.exit(1)


    # Set up logging
    logging_handler = LoggingHandler(
        logger_name="folder_copy",
        log_file_name=f"monitor_{args.monitor_path}_to_{args.destination_path}.log",
        config_file=args.monitor_config_path,
        config_section="folder_copy",
    )

    logger = logging_handler.logger     
    rclone_handler = RcloneHandler(args.destination_path, args.base_path, args.sync_mode, logger)
    logger.info(f"Start copying files from {args.monitor_path} to {args.destination_path} with base path {args.base_path} and sync mode {args.sync_mode}")
    rclone_handler.copy(args.monitor_path, True)
    logger.info(f"Finished copying files from {args.monitor_path} to {args.destination_path} with base path {args.base_path} and sync mode {args.sync_mode}")

