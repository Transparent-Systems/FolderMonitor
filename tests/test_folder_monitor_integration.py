"""
Version: 1.1

This script runs integration tests for a monitor configured in a config.yaml file.
It uses the unittest framework to execute tests sequentially.
The script depends on a folder_monitor running in a separate process.

Pre-requisites:
Start folder_monitor using the same config.yaml file as this script.
"""

import argparse
import logging.handlers
import sys
import logging
import time
import yaml
import shutil
import unittest
from pathlib import Path

# Add the scripts directory to the Python path
scriptspath = Path(__file__).parent / Path("../scripts")
sys.path.insert(0, scriptspath.resolve().as_posix())

from config_models import ConfigModels
from rclone_handler import RcloneHandler
from utils.testing_util import create_test_data, delete_test_data, create_big_file
from utils.rclone_util import CheckPath
from utils.logging_util import get_unique_logger

class TestFolderMonitorIntegration(unittest.TestCase):
    """
    Integration tests for FolderMonitor.
    This class is dynamically configured with monitor settings before execution.
    """
    monitor_config = {}
    logger = None
    check_delay = 1

    @classmethod
    def setUpClass(cls):
        if not cls.monitor_config:
            raise ValueError("Monitor config not set for TestFolderMonitorIntegration")
        
        cls.source_path = cls.monitor_config.get("monitor_path")
        cls.destination_path = cls.monitor_config.get("destination_path")
        cls.monitor_name = cls.monitor_config.get("name")
        
        # Determine appropriate check delay based on debounce settings
        # Default debounce is 2.0s. We need to wait at least that long plus some buffer.
        debounce_delay = cls.monitor_config.get("debounce_delay", 2.0)
        min_required_delay = debounce_delay + 1.0
        
        if cls.check_delay < min_required_delay:
            cls.logger.info(f"Adjusting check_delay from {cls.check_delay}s to {min_required_delay}s to account for debounce ({debounce_delay}s).")
            cls.check_delay = min_required_delay

        # Setup RcloneHandler and CheckPath
        cls.rclone_handler = RcloneHandler(
            base_destination_path=cls.destination_path,
            base_source_path=cls.source_path,
            logger=cls.logger,
            rclone_flags="",
        )
        cls.check_path = CheckPath(rclone_handler=cls.rclone_handler, check_delay=cls.check_delay)
        
        cls.logger.info(f"Setting up tests for monitor: {cls.monitor_name}")

    def setUp(self):
        """Run before each test"""
        pass

    def tearDown(self):
        """Run after each test"""
        pass

    def test_01_create_new_file(self):
        """Test 1: Create new file"""
        self.logger.info("==> Test 1: Create new file")
        file_name = "test1.txt"
        
        # Ensure clean state
        delete_test_data(path=self.source_path, files=[file_name])
        
        file_path = create_test_data(path=self.source_path, files=[file_name])
        head = file_path.parent
        tail = file_path.name
        dst_path = self.rclone_handler.get_destination_path(path=head)
        
        (found, files) = self.check_path.file_exists(parent_path=dst_path, file_name=tail)
        self.assertTrue(found, f"File {tail} should exist at {dst_path}. Files found: {files}")

    def test_02_delete_file(self):
        """Test 2: Delete a file"""
        self.logger.info("==> Test 2: Delete a file")
        file_name = "test1.txt"
        
        # Ensure file exists first (setup)
        create_test_data(path=self.source_path, files=[file_name])
        # Wait for sync
        time.sleep(self.check_delay)
        
        file_path = delete_test_data(path=self.source_path, files=[file_name])
        self.logger.debug(f"Deleted source file : '{file_path}'")
        
        head = file_path.parent
        tail = file_path.name
        dst_path = self.rclone_handler.get_destination_path(path=head)
        
        (found, files) = self.check_path.file_exists(parent_path=dst_path, file_name=tail)
        self.assertFalse(found, f"File {tail} should NOT exist at {dst_path}. Files found: {files}")

    def test_03_create_subfolder_with_files(self):
        """Test 3: Create subfolder with files. Check last file only"""
        self.logger.info("==> Test 3: Create subfolder with files")
        files = [
            "Subfolder3/test1.txt",
            "Subfolder3/test2.txt",
            "Subfolder3/test3.txt"
        ]
        
        # Clean
        delete_test_data(path=self.source_path, files=["Subfolder3"])
        time.sleep(self.check_delay)
        file_path = create_test_data(path=self.source_path, files=files)
        head = file_path.parent
        tail = file_path.name
        dst_path = self.rclone_handler.get_destination_path(path=head)

        (found, files) = self.check_path.file_exists(parent_path=dst_path, file_name=tail)
        self.assertTrue(found, f"File {tail} should exist at {dst_path}. Files found: {files}")

    def test_04_delete_subfolder(self):
        """Test 4: Delete subfolder"""
        self.logger.info("==> Test 4: Delete subfolder")
        files = ["Subfolder4/test1"]
        
        # Setup
        file_path_files = create_test_data(path=self.source_path, files=files)
        # Wait for sync
        time.sleep(self.check_delay)
        
        file_path = delete_test_data(path=self.source_path, files=["Subfolder4"])
        head = file_path.parent
        tail = file_path.name
        dst_path = self.rclone_handler.get_destination_path(path=head)
        
        # Check folder exists
        (found, files) = self.check_path.folder_exists(parent_path=dst_path, folder_name=tail)

        if found:
            # This can happen on local storage, subfolder must be empty
            # Check if the file inside is gone
            head_file = file_path_files.parent
            tail_file = file_path_files.name
            dst_path_file = self.rclone_handler.get_destination_path(path=head_file)
            (found_file, files_file) = self.check_path.file_exists(parent_path=dst_path_file, file_name=tail_file)
            self.assertFalse(found_file, f"File {tail_file} inside deleted folder should not exist.")
        else:
            self.assertFalse(found, f"Folder {tail} should not exist at {dst_path}.")

    def test_05_rename_file(self):
        """Test 5: Rename file"""
        self.logger.info("==> Test 5: Rename file")
        files = ["old_file.txt"]
        
        # Clean
        delete_test_data(path=self.source_path, files=["old_file.txt", "new_file.txt"])
        
        old_file_path = create_test_data(path=self.source_path, files=files)
        # Wait for creation sync
        time.sleep(self.check_delay)
        
        # Rename the file
        new_file_path = Path(self.source_path) / Path("new_file.txt")
        if new_file_path.exists():
            new_file_path.unlink()

        old_file_path.rename(new_file_path)

        # Check if old file has been deleted from destination
        head = old_file_path.parent
        tail = old_file_path.name
        dst_path = self.rclone_handler.get_destination_path(path=head)
        (found, files) = self.check_path.file_exists(parent_path=dst_path, file_name=tail)
        self.assertFalse(found, f"Old file {tail} should not exist at {dst_path}.")

        # Check if new file exists at destination
        head = new_file_path.parent
        tail = new_file_path.name
        dst_path = self.rclone_handler.get_destination_path(head)
        (found, files) = self.check_path.file_exists(parent_path=dst_path, file_name=tail)
        self.assertTrue(found, f"New file {tail} should exist at {dst_path}.")

    def test_06_rename_subfolder(self):
        """Test 6: Rename subfolder"""
        self.logger.info("==> Test 6: Rename subfolder")
        files = ["Subfolder-old/test1.txt", "Subfolder-old/test2.txt"]
        
        # Clean
        if (Path(self.source_path) / "Subfolder-old").exists():
            shutil.rmtree(Path(self.source_path) / "Subfolder-old")
        if (Path(self.source_path) / "Subfolder-new").exists():
            shutil.rmtree(Path(self.source_path) / "Subfolder-new")
            
        file_path = create_test_data(path=self.source_path, files=files)
        # Wait for creation sync
        time.sleep(self.check_delay + 1)

        # Rename Subfolder-old to Subfolder-new
        new_path = Path(self.source_path) / Path("Subfolder-new")
        head_old = file_path.parent
        head_old.replace(target=new_path.as_posix())
        
        head_new = new_path / file_path.name # Reconstruct path to file in new folder

        # Check if Subfolder-old has been deleted from destination
        # We check the folder itself
        head_old_folder = Path(self.source_path) / "Subfolder-old"
        dst_path_old = self.rclone_handler.get_destination_path(head_old_folder.parent)
        (found, files) = self.check_path.folder_exists(parent_path=dst_path_old, folder_name="Subfolder-old")
        self.assertFalse(found, "Old subfolder should not exist at destination.")

        # Check if new folder exists at destination
        dst_path_new = self.rclone_handler.get_destination_path(new_path.parent)
        (found, files) = self.check_path.folder_exists(parent_path=dst_path_new, folder_name="Subfolder-new")
        self.assertTrue(found, "New subfolder should exist at destination.")

    def test_07_write_big_file(self):
        """Test 7: Write big file"""
        self.logger.info("==> Test 7: Write big file")
        file_name = "big-test-file.txt"

        # Delete big file first
        delete_test_data(path=self.source_path, files=[file_name])
        
        dst_path = self.rclone_handler.get_destination_path(path=Path(self.source_path) / file_name)
        (found, isdir, files) = self.check_path.path_exists(path=dst_path)
        self.assertFalse(found, "Big file should not exist at destination before creation.")

        # Create big file
        file_path = create_big_file(path=self.source_path, filename=file_name, write_duration_seconds=15)

        # Wait before checking
        time.sleep(5 + self.check_delay)
        dst_path = self.rclone_handler.get_destination_path(path=file_path)
        (found, isdir, files) = self.check_path.path_exists(path=dst_path)
        self.assertTrue(found, f"Big file should exist at destination: {dst_path}")

    def test_08_write_many_files(self):
        """Test 8: Write many files"""
        self.logger.info("==> Test 8: Write many files")
        
        max_file_count = 4
        file_paths = []
        
        # Clean
        for i in range(1, max_file_count):
            file_name = f"many_files_{i}.txt"
            delete_test_data(path=self.source_path, files=[file_name])
            file_paths.append(Path(self.source_path) / file_name)
            
        time.sleep(self.check_delay)

        # Verify delete for last file only
        file_path = file_paths[-1]
        dst_path = self.rclone_handler.get_destination_path(path=file_path)
        (found, isdir, files) = self.check_path.path_exists(path=dst_path)
        self.assertFalse(found, f"File {file_path.name} should not exist at destination.")
        # for file_path in file_paths:

        # Create many files
        created_paths = []
        for i in range(1, max_file_count):
            file_name = f"many_files_{i}.txt"
            file_path = create_test_data(path=self.source_path, files=[file_name])
            created_paths.append(file_path)

        # Wait
        time.sleep(self.check_delay + 2)

        # Verify creation of last file only
        file_path = created_paths[-1]
        dst_path = self.rclone_handler.get_destination_path(path=file_path)
        (found, isdir, files) = self.check_path.path_exists(path=dst_path)
        self.assertTrue(found, f"File {file_path.name} should exist at destination.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run integration tests for folder monitors using unittest."
    )
    parser.add_argument(
        "--config-path",
        type=str,
        default="conf/config.tests.yaml",
        help="Path to monitor configuration file."
    )
    parser.add_argument(
        "--log-file_name",
        type=str,
        default="monitor_integration_test.log",
        help="Log file name."
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="DEBUG",
        help="Log level."
    )
    parser.add_argument(
        "--check-delay",
        type=float,
        default=1.0,
        help="Delay in seconds to wait before checking results."
    )
    args = parser.parse_args()

    # Setup logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    
    # Clean handlers
    for h in root_logger.handlers[:]:
        root_logger.removeHandler(h)

    # Console Handler
    console_handler = logging.StreamHandler()
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(name)s - %(message)s")
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # Load Config
    if not ConfigModels().validate(config_path=args.config_path, logger=root_logger):
        root_logger.error(f"Configuration file '{args.config_path}' is invalid.")
        sys.exit(1)

    with open(args.config_path, "r") as file:
        monitor_config = yaml.safe_load(file)

    # Setup File Logging
    log_config = monitor_config.get("logging", {})
    LOG_FILE = log_config.get("log_file_name", args.log_file_name)
    LOG_FOLDER = log_config.get("log_folder", "logs")
    MAX_BYTES = log_config.get("max_bytes", 10 * 1024 * 1024)
    BACKUP_COUNT = log_config.get("backup_count", 5)

    log_folder_path = Path(LOG_FOLDER)
    if not log_folder_path.exists():
        log_folder_path.mkdir(parents=True)

    file_handler = logging.handlers.RotatingFileHandler(
        (log_folder_path / LOG_FILE).as_posix(),
        maxBytes=MAX_BYTES,
        backupCount=BACKUP_COUNT
    )
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    logger = get_unique_logger(args.log_level)
    logger.info("Starting Integration Tests")

    monitors = monitor_config.get("monitors", [])
    
    overall_success = True

    for monitor in monitors:
        if not monitor.get("enabled"):
            logger.info(f"Skipping disabled monitor: {monitor.get('name')}")
            continue

        monitor_path = Path(monitor.get("monitor_path"))
        if not monitor_path.exists():
            monitor_path.mkdir(parents=True)

        # Inject configuration into Test Class
        testing_config = monitor.get("testing", {})
        check_delay = testing_config.get("check_delay", args.check_delay)
        
        TestFolderMonitorIntegration.monitor_config = monitor
        TestFolderMonitorIntegration.logger = logger
        TestFolderMonitorIntegration.check_delay = check_delay

        logger.info(f"Running tests for monitor: {monitor.get('name')}")
        
        # Run Tests
        suite = unittest.TestLoader().loadTestsFromTestCase(TestFolderMonitorIntegration)
        result = unittest.TextTestRunner(verbosity=2).run(suite)
        
        if not result.wasSuccessful():
            overall_success = False
            logger.error(f"Tests failed for monitor: {monitor.get('name')}")

    if not overall_success:
        sys.exit(1)
    
    logger.info("All tests passed successfully.")