"""
Author: John Zoetebier
Date: 2025-05-10
Description: 
    This script starts one or more monitors from a monitor_entries.txt file.
    Each line represents a single monitor.
    The format of a line is the same as the parameters of folder_monitor.py.
    Run ";python folder_monitor.py -h" for usage and paramaters.

    The script starts a folder monitor for each line in the file.
    The script uses the MonitorEntryProcessor class to read the entries from the file.
    The script uses the file_monitor.start_monitor function to start the monitor.
    The script is designed to run indefinitely, monitoring the specified folders for changes.

    You can stop the script by pressing Ctrl+C in the terminal.
    Make sure you have Python installed on your system. You can download it from https://www.python.org/downloads/
    To install Python, follow the instructions on the official website.
    After installing Python, you can run the script using the command line or terminal.
    Open a command prompt or terminal window and navigate to the directory where the script is saved.
    Use the command `cd path_to_directory` to navigate to the directory where the script is saved.
    For example, if the script is saved in the "C:\\scripts" directory, you would use:
    cd C:\\scripts
    Then, run the script using the command:
    python folder_monitor_batch.py --monitor-entries-path <path>
    Replace <path> with the actual path to the file with monitor entries.

    Call examples:
        python folder_monitor_batch.py --monitor-entries-path "D:\\Scripts\\data\\monitor_entries.txt"
        python folder_monitor_batch.py --monitor-entries-path "D:/Scripts/data/monitor_entries.txt"
        python folder_monitor_batch.py --monitor-entries-path "/home/username/scripts/data/monitor_entries.txt"

    Make sure to use the actual path to the file with monitor entries.
    The double backslashes are used to escape the backslash character in Python strings. Use single backslashes when actually calling the script.
    Alternatively, use forward slashes in the path name
"""

import argparse
import sys
import os
import time
import configparser

from logging_handler import LoggingHandler
from monitor_entries import MonitorEntryProcessor
from folder_monitor import MonitorHandler

if __name__ == "__main__":
    print("This is file_monitor_batch script.")
    parser = argparse.ArgumentParser(description="This script reads entries from a file and start a folder monitor for each line.")
    parser.usage = "python folder_monitor_batch.py --monitor-entries-path <path>"
    parser.add_argument("--monitor-entries-path", type=str, help="The path of a file with monitor entries", required=True)

    args = parser.parse_args()

    # Create instance of LoggingHandler
    logging_handler = LoggingHandler(
        logger_name="folder_monitor_batch",
        log_file_name="folder_monitor_batch.log",
        config_file="monitor.ini",
        config_section="folder_monitor_batch",
        )
    
    logger = logging_handler.logger
    logger.info("file_monitor_batch script started.")
    logger.info(f"Monitor entries path: {args.monitor_entries_path}")

    monitor_entry_processor = MonitorEntryProcessor(args.monitor_entries_path, logger)
    monitors = set()
    while True:
        entry = monitor_entry_processor.next_entry()
        if entry is None:
            break

        if 'base_path' not in entry:
            entry['base_path'] = ""
        if 'sync_mode' not in entry:
            entry['sync_mode'] = "False"
        logger.info("==========================")
        logger.info(f"Destination Path: {entry['destination_path']}")
        logger.info(f"Monitor Path: {entry['monitor_path']}")
        logger.info(f"Base Path: {entry['base_path'] if 'base_path' in entry else ''}")
        logger.info(f"Sync Mode: {entry['sync_mode'] if 'sync_mode' in entry else 'False'}")

        # Create an instance of MonitorHandler for each entry
        monitor_handler = MonitorHandler(
            monitor_path=entry['monitor_path'],
            destination_path=entry['destination_path'],
            base_path=entry['base_path'],
            sync_mode=entry['sync_mode'],
            monitor_config_path="monitor.ini",
            )
        # Start the monitor
        logger.info(f"Starting monitor for {entry['monitor_path']} to {entry['destination_path']}")
        # Use the start_monitor method to start the monitor
        # The start_monitor method is not blocking, so we can start multiple monitors
        # without waiting for each one to finish
        monitor_handler.start_monitor()
        monitors.add(monitor_handler)
        # break # Remove this break to start all processes

    logger.info("Main process continues to run")
    logger.info("Press Ctrl+C to stop the monitor...")

    # Keep the script running until interrupted by the user or a signal
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt received. Stopping the monitor...")
    except SystemExit:
        logger.info("SystemExit received. Stopping the monitor...")
    finally:
        # Wait for all processes to finish
        logger.info("Waiting for all processes to finish...")
        for monitor in monitors:
            logger.info(f"Stopping monitor for {monitor.monitor_path}")
            monitor.stop_monitor()
        logger.info("All monitors finished.")

    logger.info("file_monitor_batch script finished.")