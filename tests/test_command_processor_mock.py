import argparse
import sys
import logging
import unittest
from unittest.mock import patch
import io
from pathlib import Path

# Add the scripts directory to the Python path
scriptspath = Path(__file__).parent / Path("../scripts")
sys.path.insert(0, scriptspath.resolve().as_posix())

from command_processor import CommandProcessor
from utils.logging_util import get_unique_logger

class TestCommandProcessor(unittest.TestCase):
    logger: logging.Logger
    db_path: str

    @classmethod
    def setUpClass(cls):
        if not cls.db_path:
            raise ValueError("Database path not set for TestCommandProcessor")
        
        cls.logger.info(f"Setting up tests for CommandProcessor with db: {cls.db_path}")

    def setUp(self):
        """Set up for each test by mocking dependencies."""
        # We patch the modules where they are LOOKED UP, which is inside the command_processor module.
        self.patcher_sqlite = patch('command_processor.SQLiteHandler')
        self.patcher_diagnostic = patch('command_processor.DiagnosticUtil')
        self.patcher_s3_factory = patch('command_processor.S3Factory')
        self.patcher_rclone_handler = patch('command_processor.RcloneHandler')
        self.patcher_profile_handler = patch('command_processor.ProfileHandler')

        self.mock_sqlite_handler = self.patcher_sqlite.start()
        self.mock_diagnostic_util = self.patcher_diagnostic.start()
        self.mock_s3_factory = self.patcher_s3_factory.start()
        self.mock_rclone_handler = self.patcher_rclone_handler.start()
        self.mock_profile_handler = self.patcher_profile_handler.start()

        # Instantiate the class under test
        self.command_processor = CommandProcessor(logger=self.logger, db_path=self.db_path)

    def tearDown(self):
        """Clean up after each test."""
        patch.stopall()

    @patch('sys.stdout', new_callable=io.StringIO)
    def test_01_command_version(self, mock_stdout):
        """Test the version command."""
        self.logger.debug(f"==> {self._testMethodName}")
        self.command_processor.process_command("version", "", {})
        output = mock_stdout.getvalue().strip()
        self.assertIn("FolderMonitor v", output)

    @patch('sys.stdout', new_callable=io.StringIO)
    def test_02_command_config_file(self, mock_stdout):
        """Test the config file command."""
        self.logger.debug(f"==> {self._testMethodName}")
        self.command_processor.process_command("config", "file", {"db_path": self.db_path})
        output = mock_stdout.getvalue().strip()
        self.assertIn(f"Config location: {self.db_path}", output)

    def test_03_command_test(self):
        """Test the main test command."""
        self.logger.debug(f"==> {self._testMethodName}")
        mock_instance = self.mock_diagnostic_util.return_value
        mock_instance.check_app_env.return_value = True
        mock_instance.check_rclone_dependency.return_value = True
        mock_instance.check_app_config.return_value = True

        self.command_processor.config_test()

        mock_instance.check_app_env.assert_called_once()
        mock_instance.check_profile_import.assert_called_once()
        mock_instance.check_rclone_dependency.assert_called_once()
        mock_instance.check_app_config.assert_called_once()
        mock_instance.print_overview.assert_called_once()

    @patch('sys.stdout', new_callable=io.StringIO)
    def test_04_command_profile_test_s3_with_id(self, mock_stdout):
        """Test profile test command for an S3 profile when ID is provided."""
        self.logger.debug(f"==> {self._testMethodName}")

        profile_id = 42
        profile_name = "my-s3-profile"
        mock_profile = {
            "id": profile_id,
            "name": profile_name,
            "config": {"handler": "foldermonitor"}
        }

        self.command_processor.sqlite_handler.get_profile.return_value = mock_profile
        mock_s3_client = self.mock_s3_factory.return_value.get_client_from_remote
        mock_s3_client.return_value.list_buckets.return_value = {"Buckets": [{"Name": "bucket-1"}]}

        self.command_processor.profile_test(profile_id=profile_id)

        # This assertion confirms the buggy behavior of passing an ID instead of a name
        self.mock_s3_factory.return_value.get_client_from_remote.assert_called_with(profile_name=profile_id)

        output = mock_stdout.getvalue()
        self.assertIn(f"You selected profile id: {profile_id}", output)
        self.assertIn(f"You selected profile name: {profile_name}", output)
        self.assertIn("Bucket: bucket-1", output)
        self.assertIn(f"Test for profile '{profile_id}' successful", output)

    @patch('sys.stdout', new_callable=io.StringIO)
    def test_05_command_profile_test_rclone_with_id(self, mock_stdout):
        """Test profile test command for an rclone profile when ID is provided."""
        self.logger.debug(f"==> {self._testMethodName}")

        profile_id = 43
        profile_name = "my-rclone-profile"
        mock_profile = {"id": profile_id, "name": profile_name, "config": {"handler": "rclone"}}

        self.command_processor.sqlite_handler.get_profile.return_value = mock_profile
        mock_rclone_instance = self.mock_rclone_handler.return_value
        mock_rclone_instance.run_command.return_value = (0, "   12345 my-dir")

        self.command_processor.profile_test(profile_id=profile_id)

        self.mock_rclone_handler.assert_called_with(
            logger=self.command_processor.logger,
            base_source_path="profile_test_temp_source",
            base_remote_path=f"{profile_name}:",
            remote_profile=profile_name
        )
        mock_rclone_instance.run_command.assert_called_with(rclone_parms=['lsd'])

        output = mock_stdout.getvalue()
        self.assertIn(f"Connection successful to remote profile name: {profile_name}", output)

    @patch('sys.stdout', new_callable=io.StringIO)
    @patch('builtins.input', side_effect=['1', '1'])
    def test_06_command_profile_delete(self, mock_input, mock_stdout):
        """Test profile delete command (interactive)."""
        self.logger.debug(f"==> {self._testMethodName}")
        
        mock_profile_instance = self.mock_profile_handler.return_value
        mock_profile_instance.get_profile_names.return_value = ['profile-to-delete']
        mock_profile_instance.delete_profile.return_value = True

        self.command_processor.profile_delete()

        mock_profile_instance.get_profile_names.assert_called_once()
        mock_profile_instance.delete_profile.assert_called_with(profile_name='profile-to-delete')
        
        output = mock_stdout.getvalue()
        self.assertIn("You want to delete profile: profile-to-delete", output)
        self.assertIn("Profile name: profile-to-delete deleted", output)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run unit tests for CommandProcessor.")
    parser.add_argument(
        "-d", "--db-path",
        type=str,
        default="tests/data/test_command_processor.sqlite",
        help="Path to a temporary test database."
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
    
    for h in root_logger.handlers[:]:
        root_logger.removeHandler(h)

    console_handler = logging.StreamHandler()
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(name)s - %(message)s")
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    logger = get_unique_logger(args.log_level)
    logger.info("Starting CommandProcessor Unit Tests")

    TestCommandProcessor.db_path = args.db_path
    TestCommandProcessor.logger = logger

    loader = unittest.TestLoader()
    full_suite = loader.loadTestsFromTestCase(TestCommandProcessor)

    if args.test_cases:
        patterns = []
        for item in args.test_cases:
            patterns.extend(item.split())

        suite = unittest.TestSuite()
        for test in full_suite:
            if isinstance(test, unittest.TestCase):
                if any(pattern in test._testMethodName for pattern in patterns):
                    suite.addTest(test)
        
        if suite.countTestCases() == 0:
            logger.warning(f"No tests matched patterns: {patterns}")
    else:
        suite = full_suite

    result = unittest.TextTestRunner(verbosity=2).run(suite)
    
    if not result.wasSuccessful():
        logger.error("Some tests failed.")
    else:
        logger.info("All tests passed successfully.")
