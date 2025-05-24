import os
import sys
import shlex

class MonitorEntryProcessor:
    """
    A class to process monitor entries from a file.
    The file should contain key-value pairs in the format:
    --key1 value1 --key2 value2
    Lines starting with "#" are treated as comments and ignored.
    Empty lines are also ignored.
    The keys are converted to snake_case and the values are stored in a dictionary.
    """

    def __init__(self, monitor_entries_path, logger):
        self.monitor_entries_path = monitor_entries_path
        self.logger = logger
        self.logger.debug("In constructor of MonitorEntryProcessor")

        if not os.path.exists(self.monitor_entries_path):
            self.logger.debug(f"Monitor entries file not found: {self.monitor_entries_path}")
            sys.exit(1)
        if not os.path.isfile(self.monitor_entries_path):
            self.logger.debug(f"Monitor entries path is not a file: {self.monitor_entries_path}")
            sys.exit(1)
        if not os.access(self.monitor_entries_path, os.R_OK):
            self.logger.debug(f"Monitor entries file is not readable: {self.monitor_entries_path}")
            sys.exit(1)

        self.file = open(self.monitor_entries_path, 'r')

    def next_entry(self):
        line = self.file.readline()
        if not line:
            self.file.close()
            return None

        # Skip lines starting with "#"
        if line.startswith("#"):
            return self.next_entry()

        # Skip empty lines
        if line.strip() == "":
            return self.next_entry()

        # Parse the line into key-value pairs
        tokens = shlex.split(line)
        entry_dict = {}
        for i in range(0, len(tokens), 2):
            key = tokens[i].lstrip('--').replace('-', '_')
            value = tokens[i + 1]
            entry_dict[key] = value
        
        return entry_dict

    def __del__(self):
        if self.file:
            self.file.close()
            self.file = None

        self.logger.debug(f"Monitor entries file closed: {self.monitor_entries_path}")
        self.monitor_entries_path = None
        self.file = None
