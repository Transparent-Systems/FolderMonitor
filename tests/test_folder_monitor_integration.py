"""
Version: 2.0.0

This script runs integration tests for a monitor configured in a config.yaml file.
It uses the unittest framework to execute tests sequentially.
The script depends on a folder_monitor running in a separate process.

Pre-requisites:
    Start folder_monitor using the same config.yaml file as this script.

TODO:
    This class was originally for testing rclone only.
    On v2.0.0 we have a S3Handler as well.
    The script needs to be adapted working on both RcloneHandler and S3Handler.
    This can be implemented by instantiating and instance of RcloneHandler or S3Handler.
    Assign the instance to cls.base_handler which is an instance of type BaseHandler
    In the test cases we use self.base_handler to verify the remote state.
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
from s3_handler import S3Handler
from profile_handler import ProfileHandler
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

        """
        If remote_profile is missing or empty then the remote is a local file system or a folder share
        If the remote_profile is not empty, then it must be present in the rclone config file.
        The reason is that we use rclone to perform all tests.
        So, even if remote_profile is in foldermonitor config file, there must be a similar remote_profile in the rclone config file
        Currently, if remote_profile is in folder_monitor config file, then it will be handled by the internal S3Handler.
        """


        remote_profiles = cls.monitor_config.get("remote_profiles")
        # If there are no remote profiles, then add emtory remote_profile (local file system)
        if (remote_profiles is None):
            remote_profiles = []
        if (len(remote_profiles) == 0):
            remote_profiles.append("")
        
        cls.source_path = cls.monitor_config.get("monitor_path")
        cls.remote_path = cls.monitor_config.get("remote_path")
        cls.monitor_name = cls.monitor_config.get("name")
        testing_config = cls.monitor_config.get("testing", {})
        cls.check_delay = testing_config.get("check_delay", 1)

        profile_handlers: dict[str, ProfileHandler] = {}
        # Create ProfileHandler
        app_names = ["foldermonitor", "rclone"]
        for app_name in app_names:
            profile_handlers[app_name] = ProfileHandler(
                logger=cls.logger,
                app_name=app_name
            )

        for remote_profile in remote_profiles:
            if (profile_handlers["foldermonitor"].get_profile(profile_name=remote_profile)):
                # Instantiate S3Handler
                cls.base_handler = S3Handler(
                    logger=cls.logger,
                    base_source_path=cls.source_path,
                    base_remote_path=cls.remote_path,
                    remote_profile=remote_profile    
                    )
                break
            elif (profile_handlers["rclone"].get_profile(profile_name=remote_profile)):
                # Instantiate RcloneHandler
                cls.base_handler = RcloneHandler(
                    logger=cls.logger,
                    base_source_path=cls.source_path,
                    base_remote_path=cls.remote_path,
                    remote_profile=remote_profile    
                    )
                break
            else:
                if (remote_profile.strip() == ""):
                    # Instantiate RcloneHandler
                    cls.base_handler = RcloneHandler(
                        logger=cls.logger,
                        base_source_path=cls.source_path,
                        base_remote_path=cls.remote_path,
                        remote_profile=remote_profile    
                        )
                    break

        if (cls.base_handler is None):
            logger.info("Could not find a remote_profile for either foldermonitor or rclone.")
            raise ValueError("This script requires at least 1 valid remote profile to run.")

        # Setup CheckPath
        cls.check_path = CheckPath(base_handler=cls.base_handler, check_delay=cls.check_delay)
        cls.logger.info(f"Ready setUpClass for monitor: {cls.monitor_name}")

    def setUp(self):
        """Run before each test"""
        pass

    def tearDown(self):
        """Run after each test"""
        pass

    def test_01_create_new_file(self):
        """Create new file"""
        self.logger.debug(f"==> Monitor {self.monitor_name} -> {self._testMethodName}")
        file_name = "test1.txt"
        
        # Ensure clean state
        delete_test_data(path=self.source_path, files=[file_name])
        
        file_path = create_test_data(path=self.source_path, files=[file_name])
        remote_path = self.base_handler.get_remote_path(source_path=file_path)
        result_code, _ = self.check_path.file_exists(remote_path=remote_path)
        self.assertEqual(result_code, 0, f"File {file_name} should exist at {remote_path}.")

    def test_02_delete_file(self):
        """Delete a file"""
        self.logger.debug(f"==> Monitor {self.monitor_name} -> {self._testMethodName}")
        file_name = "test1.txt"
        
        # Ensure file exists first (setup)
        create_test_data(path=self.source_path, files=[file_name])
        # Wait for sync
        time.sleep(self.check_delay)
        file_path = delete_test_data(path=self.source_path, files=[file_name])
        self.logger.debug(f"Deleted source file : '{file_path}'")
        remote_path = self.base_handler.get_remote_path(source_path=file_path)
        result_code, _ = self.check_path.file_exists(remote_path=remote_path)
        self.assertEqual(result_code, 1, f"File {file_name} should not exist at {remote_path}.")

    def test_03_create_subfolder_with_files(self):
        """Create subfolder with files. Check last file only"""
        self.logger.debug(f"==> Monitor {self.monitor_name} -> {self._testMethodName}")
        files = [
            "Subfolder3/test1.txt",
            "Subfolder3/test2.txt",
            "Subfolder3/test3.txt"
        ]
        
        # Clean up
        delete_test_data(path=self.source_path, files=["Subfolder3"])
        time.sleep(self.check_delay)
        file_path = create_test_data(path=self.source_path, files=files)
        remote_path = self.base_handler.get_remote_path(source_path=file_path)
        result_code, _ = self.check_path.file_exists(remote_path=remote_path)
        self.assertEqual(result_code, 0, f"File {remote_path} should exist.")

    def test_04_delete_subfolder(self):
        """Delete subfolder"""
        self.logger.debug(f"==> Monitor {self.monitor_name} -> {self._testMethodName}")
        # Wait for sync
        time.sleep(self.check_delay)

        file_path = delete_test_data(path=self.source_path, files=["Subfolder4"])
        remote_path = self.base_handler.get_remote_path(source_path=file_path)
        result_code, _ = self.check_path.file_exists(remote_path=remote_path)
        self.assertNotEqual(result_code, 0, f"File {remote_path} should not exist.")
        
    def test_05_rename_file(self):
        """Rename file"""
        self.logger.debug(f"==> Monitor {self.monitor_name} -> {self._testMethodName}")
        files = ["old_file.txt"]
        
        # Clean
        delete_test_data(path=self.source_path, files=["old_file.txt", "new_file.txt"])
        
        old_file_path = create_test_data(path=self.source_path, files=files)
        # Wait for files to be created
        time.sleep(self.check_delay)
        
        # Rename the file
        new_file_path = Path(self.source_path) / Path("new_file.txt")
        if new_file_path.exists():
            new_file_path.unlink()

        old_file_path.rename(new_file_path)

        # Check if old file has been deleted from destination
        remote_path = self.base_handler.get_remote_path(source_path=old_file_path)
        result_code, _ = self.check_path.file_exists(remote_path=remote_path)
        self.assertEqual(result_code, 0, f"Old file {remote_path} should not exist.")

        # Check if new file exists at destination
        remote_path = self.base_handler.get_remote_path(source_path=new_file_path)
        result_code, _ = self.check_path.file_exists(remote_path=remote_path)
        self.assertEqual(result_code, 0, f"New file {remote_path} should exist.")

    def test_06_rename_subfolder(self):
        """Rename subfolder"""
        self.logger.debug(f"==> Monitor {self.monitor_name} -> {self._testMethodName}")
        files = ["Subfolder-old/test1.txt", "Subfolder-old/test2.txt"]
        
        # Cleanup
        if (Path(self.source_path) / "Subfolder-old").exists():
            shutil.rmtree(Path(self.source_path) / "Subfolder-old")
        if (Path(self.source_path) / "Subfolder-new").exists():
            shutil.rmtree(Path(self.source_path) / "Subfolder-new")
            
        file_path = create_test_data(path=self.source_path, files=files)
        # Wait for foldermonitor upload
        time.sleep(self.check_delay + 1)

        # Rename Subfolder-old to Subfolder-new
        new_path = Path(self.source_path) / Path("Subfolder-new")
        head_old = file_path.parent
        head_old.replace(target=new_path.as_posix())
        
        # Check if new file exists at remote
        new_path = Path(self.source_path) / "Subfolder-new" / "test1.txt"
        remote_path = self.base_handler.get_remote_path(new_path)
        result_code, _ = self.check_path.file_exists(remote_path=remote_path)
        self.assertEqual(result_code, 0, f"New file {remote_path} should exist.")

    def test_07_write_big_file(self):
        """Write big file"""
        self.logger.debug(f"==> Monitor {self.monitor_name} -> {self._testMethodName}")
        file_name = "big-test-file.txt"

        # Delete big file first
        delete_test_data(path=self.source_path, files=[file_name])
        # Create big file
        file_path = create_big_file(path=self.source_path, filename=file_name, write_duration_seconds=10)
        # Wait for sync
        time.sleep(self.check_delay)
        remote_path = self.base_handler.get_remote_path(source_path=file_path)
        result_code, _ = self.check_path.file_exists(remote_path=remote_path)
        self.assertEqual(result_code, 0, f"New file {remote_path} should exist.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run integration tests for folder monitors using unittest."
    )
    parser.add_argument(
        "-c",
        "--config",
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
    LOG_FILE = log_config.get("file_name", args.log_file_name)
    LOG_FOLDER = log_config.get("folder", "logs")
    MAX_BYTES = log_config.get("max_bytes", 10 * 1024 * 1024)
    BACKUP_COUNT = log_config.get("backup_count", 5)

    folder_path = Path(LOG_FOLDER)
    if not folder_path.exists():
        folder_path.mkdir(parents=True)

    file_handler = logging.handlers.RotatingFileHandler(
        (folder_path / LOG_FILE).as_posix(),
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
        loader = unittest.TestLoader()
        full_suite = loader.loadTestsFromTestCase(TestFolderMonitorIntegration)

        if args.test_cases:
            # Flatten arguments in case they were passed as a single string with spaces
            patterns = []
            for item in args.test_cases:
                patterns.extend(item.split())

            suite = unittest.TestSuite()
            for test in full_suite:
                # test._testMethodName contains the name of the test method
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

    if not overall_success:
        sys.exit(1)
    
    logger.info("All tests passed successfully.")