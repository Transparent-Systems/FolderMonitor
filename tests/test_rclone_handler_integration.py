"""
Version: 1.1

Test integration script for rclone handler.
The script iterates over monitors configured in a yaml file.
The same test suite is used for each monitor.
Refactored to use unittest.TestCase.
Ensure no folder monitor is currently running on any configured test monitor to avoid conflicts.
"""

import argparse
import sys
import logging
import yaml
import unittest
from logging.handlers import RotatingFileHandler
from pathlib import Path

# Add the scripts directory to the Python path
scriptspath = Path(__file__).parent / Path("../scripts")
sys.path.insert(0, scriptspath.resolve().as_posix())

from rclone_handler import RcloneHandler
from utils.testing_util import create_test_data
from utils.rclone_util import CheckPath
from utils.logging_util import get_unique_logger
from config_models import ConfigModels

class TestRcloneHandlerIntegration(unittest.TestCase):
    monitor_config = {}
    logger = None
    
    @classmethod
    def setUpClass(cls):
        if not cls.monitor_config:
            raise ValueError("Monitor config not set for TestRcloneHandlerIntegration")
        
        cls.monitor_name = cls.monitor_config.get("name")
        cls.logger.info(f"Setting up tests for monitor: {cls.monitor_name}")

        subfolder = "test_rclone_handler_integration"
        
        # Setup Source Path
        raw_source = cls.monitor_config.get("monitor_path")
        raw_source_stripped = raw_source.rstrip('/')
        cls.source_path = f"{raw_source_stripped}/{subfolder}"
        
        # Setup Destination Path
        raw_dest = cls.monitor_config.get("destination_path")
        raw_dest_stripped = raw_dest.rstrip('/')
        cls.destination_path = f"{raw_dest_stripped}/{subfolder}"
        
        rclone_flags = cls.monitor_config.get("rclone_flags", "")

        cls.rclone_handler = RcloneHandler(
            base_destination_path=cls.destination_path,
            base_source_path=cls.source_path,
            logger=cls.logger,
            rclone_flags=rclone_flags,
        )
        
        cls.check_path = CheckPath(
            rclone_handler=cls.rclone_handler,
            check_delay=0,
        )
        
        # Ensure source directory exists
        Path(cls.source_path).mkdir(parents=True, exist_ok=True)

    def test_01_utils(self):
        """Testing utils (path_exists checks)"""
        self.logger.debug(f"==> Monitor {self.monitor_name} -> {self._testMethodName}")
        file_name = "Subfolder1/test1.txt"
        
        # Create source file
        file_path = create_test_data(path=self.source_path, files=[file_name])
        
        # Copy to remote manually to setup state
        (result_code, result_output) = self.rclone_handler.copy_file(source_path=file_path.as_posix())
        self.assertEqual(result_code, 0, f"Setup failed: copy file {file_name}. Output: {result_output}")

        # Check existing file
        dst_path = self.rclone_handler.get_destination_path(path=file_path)
        (found, isdir, files) = self.check_path.path_exists(path=dst_path)
        self.assertTrue(found, f"File should exist: {dst_path}")
        self.assertFalse(isdir, f"Path should be a file, not dir: {dst_path}")

        # Check non-existent file
        dst_path_missing = Path(self.source_path) / "file-does-not-exists.txt"
        (found, isdir, files) = self.check_path.path_exists(path=dst_path_missing)
        self.assertFalse(found, f"File should not exist: {dst_path_missing}")

        # Check existing directory
        subfolder_path = Path(self.source_path) / "Subfolder1"
        dst_path_folder = self.rclone_handler.get_destination_path(path=subfolder_path)
        (found, isdir, files) = self.check_path.path_exists(path=dst_path_folder)
        self.assertTrue(found, f"Folder should exist: {dst_path_folder}")
        self.assertTrue(isdir, f"Path should be a dir: {dst_path_folder}")

        # Check non-existent directory
        subfolder_missing = Path(self.source_path) / "folder_does_not_exist"
        dst_path_missing_folder = self.rclone_handler.get_destination_path(path=subfolder_missing)
        (found, isdir, files) = self.check_path.path_exists(path=dst_path_missing_folder)
        self.assertFalse(found, f"Folder should not exist: {dst_path_missing_folder}")

    def test_02_get_version(self):
        """Get Version"""
        self.logger.debug(f"==> Monitor {self.monitor_name} -> {self._testMethodName}")
        (result_code, result_output) = self.rclone_handler.get_rclone_version()
        self.assertIn("rclone", result_output.lower(), "Output should contain 'rclone'")

    def test_03_list_remotes(self):
        """List Remotes"""
        self.logger.debug(f"==> Monitor {self.monitor_name} -> {self._testMethodName}")
        (result_code, result_output) = self.rclone_handler.list_remotes()
        self.assertEqual(result_code, 0, f"List remotes failed. Output: {result_output}")

    def test_04_copy_file_to_remote(self):
        """Copy file to remote"""
        self.logger.debug(f"==> Monitor {self.monitor_name} -> {self._testMethodName}")
        file_name = "test1.txt"
        file_path = create_test_data(path=self.source_path, files=[file_name])
        
        (result_code, result_output) = self.rclone_handler.copy_file(source_path=file_path.as_posix())
        self.assertEqual(result_code, 0, f"Copy file failed. Output: {result_output}")

        head = file_path.parent
        tail = file_path.name
        dst_path = self.rclone_handler.get_destination_path(path=head)
        (found, files) = self.check_path.file_exists(parent_path=dst_path, file_name=tail)
        self.assertTrue(found, f"File {tail} should be found on remote at {dst_path}")

    def test_05_delete_file_at_remote(self):
        """Delete a file at remote"""
        self.logger.debug(f"==> Monitor {self.monitor_name} -> {self._testMethodName}")
        file_name = "test2.txt"
        file_path = create_test_data(path=self.source_path, files=[file_name])

        # Copy first
        (result_code, result_output) = self.rclone_handler.copy_file(source_path=file_path.as_posix())
        self.assertEqual(result_code, 0, "Setup failed: Copy file")

        # Delete
        dst_path = self.rclone_handler.get_destination_path(path=file_path)
        (result_code, result_output) = self.rclone_handler.delete_file(destination_path=dst_path)
        self.assertEqual(result_code, 0, f"Delete file failed. Output: {result_output}")

        # Check absence
        head = file_path.parent
        tail = file_path.name
        dst_parent = self.rclone_handler.get_destination_path(path=head)
        (found, files) = self.check_path.file_exists(parent_path=dst_parent, file_name=tail)
        self.assertFalse(found, f"File {tail} should be deleted from remote")

    def test_06_create_folder_with_files(self):
        """Create folder with files"""
        self.logger.debug(f"==> Monitor {self.monitor_name} -> {self._testMethodName}")
        files = ["Subfolder1/test1.txt", "Subfolder1/test2.txt", "Subfolder1/test3.txt"]
        
        # Create files
        file_path = create_test_data(path=self.source_path, files=files)
        head = file_path.parent # Subfolder1

        # Copy folder
        (result_code, result_output) = self.rclone_handler.copy_folder(source_path=head.as_posix())
        self.assertEqual(result_code, 0, f"Copy folder failed. Output: {result_output}")

        # Check one file
        dst_path = self.rclone_handler.get_destination_path(path=head.as_posix())
        file_name = file_path.name
        (found, files_found) = self.check_path.file_exists(parent_path=dst_path, file_name=file_name)
        
        self.assertTrue(found, f"File {file_name} should exist in copied folder")
        self.assertGreaterEqual(len(files_found), len(files), "Should find at least as many files as created")

    def test_07_remove_folder_from_remote(self):
        """Remove folder from remote"""
        self.logger.debug(f"==> Monitor {self.monitor_name} -> {self._testMethodName}")
        files = ["Subfolder2/test1.txt", "Subfolder2/test2.txt", "Subfolder2/test3.txt"]
        
        # Create source data first
        file_path = create_test_data(path=self.source_path, files=files)
        head = file_path.parent

        # Copy folder
        (result_code, result_output) = self.rclone_handler.copy_folder(source_path=head.as_posix())
        self.assertEqual(result_code, 0, "Rclone copy_folder succeeded")

        # Verify folder exists
        head_parent = head.parent
        folder_name = head.name
        destination_path = self.rclone_handler.get_destination_path(head_parent)
        (found, _) = self.check_path.folder_exists(parent_path=destination_path, folder_name=folder_name)
        self.assertTrue(found, "Folder {folder_name} should exist at destination")

        # Delete folder
        destination_path = self.rclone_handler.get_destination_path(head)
        (result_code, result_output) = self.rclone_handler.delete_folder(destination_path=destination_path)
        self.assertEqual(result_code, 0, f"Rclone delete_folder failed for {destination_path}. Output: {result_output}")

        # Deleted subfolder test will fail for versioned storage
        # Skip test until we find a reliable way to check for a version file system
        # head_parent = head.parent
        # folder_name = head.name
        # dst_parent_path = self.rclone_handler.get_destination_path(path=head_parent)
        # (found, _) = self.check_path.folder_exists(parent_path=dst_parent_path, folder_name=folder_name)
        # self.assertFalse(found, f"Folder {folder_name} should have been deleted from remote")

    def test_08_file_with_space(self):
        """Testing file with space"""
        self.logger.debug(f"==> Monitor {self.monitor_name} -> {self._testMethodName}")
        file_name = "Subfolder1/file with space.txt"
        file_path = create_test_data(path=self.source_path, files=[file_name])
        
        (result_code, result_output) = self.rclone_handler.copy_file(source_path=file_path.as_posix())
        self.assertEqual(result_code, 0, f"Copy file with space failed. Output: {result_output}")

        dst_path = self.rclone_handler.get_destination_path(path=file_path)
        (found, isdir, _) = self.check_path.path_exists(path=dst_path)
        self.assertTrue(found, "File with space should exist on remote")
        self.assertFalse(isdir, "Should be a file")

    def test_09_folder_with_space(self):
        """Testing folder with space"""
        self.logger.debug(f"==> Monitor {self.monitor_name} -> {self._testMethodName}")
        file_name = "Subfolder with Space/test1.txt"
        file_path = create_test_data(path=self.source_path, files=[file_name])
        
        (result_code, result_output) = self.rclone_handler.copy_file(source_path=file_path.as_posix())
        self.assertEqual(result_code, 0, f"Copy file in folder with space failed. Output: {result_output}")

        parent = file_path.parent
        dst_path = self.rclone_handler.get_destination_path(path=parent)
        (found, isdir, _) = self.check_path.path_exists(path=dst_path)
        self.assertTrue(found, "Folder with space should exist on remote")
        self.assertTrue(isdir, "Should be a directory")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run integration tests for rclone_handler using unittest."
    )
    parser.add_argument(
        "-c",
        "--config",
        type=str,
        default="conf/config.tests.yaml",
        help="Path to monitor configuration file."
    )
    parser.add_argument(
        "--log-filename",
        type=str,
        default="test_rclone_handler_integration.log",
        help="Log file name."
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="DEBUG",
        help="Log level."
    )
    parser.add_argument(
        "--test-cases",
        type=str,
        nargs="+",
        help="Space-separated list of test method names (or substrings) to run."
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
    if not ConfigModels().validate(config_path=args.config, logger=root_logger):
        root_logger.error(f"Configuration file '{args.config}' is invalid.")
        sys.exit(1)

    with open(args.config, "r") as file:
        monitor_config = yaml.safe_load(file)

    # Setup File Logging
    log_config = monitor_config.get("logging", {})
    LOG_FILE = log_config.get("log_file_name", args.log_filename)
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
    logger.info("Starting Rclone Handler Integration Tests")

    monitors = monitor_config.get("monitors", [])
    overall_success = True

    for monitor in monitors:
        if not monitor.get("enabled"):
            logger.info(f"Skipping disabled monitor: {monitor.get('name')}")
            continue

        # Inject configuration into Test Class
        TestRcloneHandlerIntegration.monitor_config = monitor
        TestRcloneHandlerIntegration.logger = logger
        
        logger.info(f"Running tests for monitor: {monitor.get('name')}")
        
        # Run Tests
        loader = unittest.TestLoader()
        full_suite = loader.loadTestsFromTestCase(TestRcloneHandlerIntegration)

        if args.test_cases:
            # Flatten arguments
            patterns = []
            for item in args.test_cases:
                patterns.extend(item.split())

            suite = unittest.TestSuite()
            for test in full_suite:
                if any(pattern in test._testMethodName for pattern in patterns):
                    suite.addTest(test)
            
            if suite.countTestCases() == 0:
                 logger.warning(f"No tests matched patterns: {patterns}")
        else:
            suite = full_suite

        result = unittest.TextTestRunner(verbosity=2).run(suite)
        
        if not result.wasSuccessful():
            overall_success = False
            logger.error(f"Tests failed for monitor: {monitor.get('name')}")

    if overall_success:
        logger.info("All tests passed successfully.")    
    else:
        logger.info("Not all tests passed successfully.")
