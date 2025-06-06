# import configparser
import yaml
import logging
from logging.handlers import RotatingFileHandler
import os
import re
import sys
import time
import datetime

class LoggingHandler:
    def __init__(self, logger_name, log_file_name, config_file, config_section):
        """
        Initialize the LoggingHandler class.
        Args:
            logger_name (str): The name of the logger.
            log_file_name (str): The name of the log file.
            config_file (str): The path to the configuration file.
            config_section (str): The section in the configuration file to read.
          
        """
        # Create a console logger first. Later on we add a rotating file logger, if possibe

        # Create a time stamp for the logger name
        # Get the current time and format it
        # to a string in the format YYYY-MM-DD_HH:MM:SS
        # Get the current time
        # Format the time to a string with milliseconds

        # Use the formatter with milliseconds for the logger name
        # Get the current datetime object with microsecond precision
        now = datetime.datetime.now()
        # Format the datetime object to include milliseconds
        timestamp_with_ms = now.strftime("%Y-%m-%d_%H:%M:%S.%f")

        # Create a logger name with the time stamp
        logger_name = f"{logger_name}_{timestamp_with_ms}"
        self.logger = logging.getLogger(logger_name)
        # Set the logger to debug level initially. Will be changed later by value on monitor.yaml
        self.logger.setLevel(logging.DEBUG)
        # Add a console handler to the logger
        console_handler = logging.StreamHandler()
        formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(name)s - %(message)s")
        console_handler.setFormatter(formatter)
        # Add the console handler to the logger
        self.logger.addHandler(console_handler)

        # Now try to create a rotating file logger
        self.logger.debug("Trying to create a rotating file logger")
        # Get path where the script is running
        script_path = os.path.dirname(os.path.abspath(__file__))

        self.logger.debug("Checking if config_file exists")
        if not os.path.isfile(config_file):
            self.logger.debug(f"Monitor config file does not exist. Prepending it with the script path: {config_file}")
            config_file = os.path.join(script_path, config_file)
            # replace backslashes with forward slashes
            config_file = config_file.replace("\\", "/")
            self.logger.debug(f"Monitor config file: {config_file}")
            # Now check again if  monitor_config_path exists
            if not os.path.isfile(config_file):
                self.logger.debug("The configuration file monitor.yaml does not exist.")
                return

        with open(config_file, 'r') as file:
            try:
                config = yaml.safe_load(file)
            except yaml.YAMLError as exc:
                self.logger.debug(f"Error reading the configuration file {config_file}: {exc}")
                return
        # Check if the config file has the section we need
        if config_section not in config:
            self.logger.debug(f"The configuration file {config_file} does not have the section {config_section}.")
            return

        # Create log folder if it does not exist
        log_folder = config[config_section]['log_folder']
        if not os.path.isdir(log_folder):
            # Prepend it with the script path
            log_folder = os.path.join(script_path, log_folder)
            self.logger.debug(f"Log folder does not exist. Prepending it with the script path: {log_folder}")
            # replace backslashes with forward slashes
            log_folder = log_folder.replace("\\", "/")
            self.logger.debug(f"Log folder: {log_folder}")
            # Check if the folder exists
            if not os.path.exists(log_folder):
                self.logger.debug(f"The folder {log_folder} does not exist. Creating it.")
                os.makedirs(log_folder)

        # Check again if log_folder exists. If not then exit
        if not os.path.isdir(log_folder):
            self.logger.debug(f"The folder {log_folder} does not exist. No rotating file logger will be created.")
            return

        # When we are here we know that the log_folder exists
        # Ensure the filename is valid
        log_file_name = re.sub(r'[^a-zA-Z0-9\.]', '_', log_file_name)
        # Convert to lowercase
        log_file_name = log_file_name.lower()
        # Remove leading/trailing underscores
        log_file_name = log_file_name.strip('_')
        # Ensure the filename is not empty
        if not log_file_name:
            self.logger.debug("Error: The generated filename is empty after sanitization.")
            return
        # Replace one or more consecutive underscores with a single underscore
        log_file_name = re.sub(r'_{2,}', '_', log_file_name)
        # Ensure the filename is not too long
        if len(log_file_name) > 255:
            self.logger.debug("Error: The generated filename is too long. Going to limit it to 255 characters.")
            log_file_name = log_file_name[:255]
        # Ensure the filename is not empty
        if not log_file_name:
            self.logger.debug("Error: The generated filename is empty after sanitization.")
            return

        # Append log_file_name to log_folder
        log_file_name = os.path.join(log_folder, log_file_name)

        # Now create a logger using the values from the config file
        self.logger.debug(f"Get log_level from configuration file: {config[config_section]['log_level']}")
        # Create a logger
        log_level = config[config_section]['log_level'].upper()
        if log_level == "DEBUG":
            self.logger.setLevel(logging.DEBUG)
        elif log_level == "INFO":
            self.logger.setLevel(logging.INFO)
        elif log_level == "WARNING":
            self.logger.setLevel(logging.WARNING)
        elif log_level == "ERROR":
            self.logger.setLevel(logging.ERROR)
        elif log_level == "CRITICAL":
            self.logger.setLevel(logging.CRITICAL)
        else:
            self.logger.setLevel(logging.NOTSET)

        # Create a rotating file handler
        # Get the max file size and backup count from the config file
        # If the values are not set, use default values
        if not config[config_section]['log_max_file_size']:
            self.logger.debug("The configuration file does not have the log_max_file_size option. Using default value of 10 MB.")
            config[config_section]['log_max_file_size'] = "10485760"  # 10 MB in bytes
        if not config[config_section]['log_max_backup_count']:
            self.logger.debug("The configuration file does not have the log_max_backup_count option. Using default value of 5.")
            config[config_section]['log_max_backup_count'] = "5"  # 5 backup files
        # Get the max file size and backup count from the config file
        max_file_size = config[config_section]['log_max_file_size']
        max_file_size = int(max_file_size)  # Ensure it's an integer
        backup_count = config[config_section]['log_max_backup_count']
        backup_count = int(backup_count)  # Ensure it's an integer
        # Check if the max file size is a valid integer
        if not isinstance(max_file_size, int) or max_file_size <= 0:
            self.logger.debug("The max file size is not a valid integer. Using default value of 10 MB.")
            max_file_size = 10485760
        # Check if the backup count is a valid integer
        if not isinstance(backup_count, int) or backup_count <= 0:
            self.logger.debug("The backup count is not a valid integer. Using default value of 5.")
            backup_count = 5
        # Check if the log file name is a valid string
        if not isinstance(log_file_name, str) or not log_file_name:
            self.logger.debug("The log file name is not a valid string. Using default value of test.log.")
            log_file_name = "test.log"

        # Create a rotating file handler
        rotating_file_handler = RotatingFileHandler(log_file_name, maxBytes=max_file_size, backupCount=backup_count)
        # Create a default formatter
        formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(name)s - %(message)s")
        rotating_file_handler.setFormatter(formatter)
        # Add the handler to the logger
        self.logger.addHandler(rotating_file_handler)

        # Log the command line arguments
        self.logger.debug(f"Command line arguments: {sys.argv}")
        # Log the current working directory
        self.logger.debug(f"Current working directory: {sys.path[0]}")
        # Log the Python version
        self.logger.debug(f"Python version: {sys.version}")
        # Log the platform
        self.logger.debug(f"Platform: {sys.platform}")
        # Log the system information
        self.logger.debug(f"System information: {sys.version_info}")
        # Log the environment variables
        # self.logger.debug(f"Environment variables: {os.environ}")
        # Log the current working directory
        self.logger.debug(f"Current working directory: {sys.path[0]}")
        # Log the current time
        self.logger.debug(f"Current time: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())}")


    def __del__(self):
        self.logger.debug("LoggingHandler __del__: Closing logger")
        handlers = self.logger.handlers[:]
        for handler in handlers:
            handler.close()
            self.logger.removeHandler(handler)

