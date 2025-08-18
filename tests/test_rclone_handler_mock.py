# tests/test_rclone_handler_mock.py
import unittest
import os
import sys
from unittest.mock import patch, MagicMock
import unittest.mock  # Import for clarity if you want to check type
import subprocess


# Add the parent directory to the Python path so we can import rclone_handler
# This assumes that the rclone_handler module is in the scripts directory
# sys.path.insert works at runtime, so we can use it to include the scripts directory
# For VS Code language server add folder scripts to extra path in workspace settings: use Quick Fix
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../mocks")))

from rclone_handler import RcloneHandler


class TestRcloneHandler(unittest.TestCase):

    def setUp(self):
        """
        Set up for test methods. This runs before each test.
        We'll mock the subprocess.run call to avoid actually running rclone commands.
        """
        self.mock_subprocess_run = patch("subprocess.run").start()
        self.rclone_handler = RcloneHandler(
            rclone_path="mock_rclone"
        )  # Use a mock path to instantiate RcloneHandler

    def tearDown(self):
        """
        Clean up after each test method. This runs after each test.
        """
        patch.stopall()  # Stop all active patches

    def test_list_remotes_success(self):
        """
        Test list_remotes when the rclone command is successful.
        """
        self.mock_subprocess_run.return_value = MagicMock(
            stdout="remote1:\nremote2:\n", stderr="", returncode=0
        )
        remotes = self.rclone_handler.list_remotes()
        self.assertEqual(remotes, "remote1:\nremote2:")
        self.mock_subprocess_run.assert_called_once_with(
            ["mock_rclone", "listremotes"], capture_output=True, text=True, check=True
        )

    def test_list_remotes_failure(self):
        """
        Test list_remotes when the rclone command fails.
        """
        self.mock_subprocess_run.side_effect = subprocess.CalledProcessError(
            returncode=1,
            cmd=["mock_rclone", "listremotes"],
            stderr="Error listing remotes",
        )
        with self.assertRaisesRegex(
            RuntimeError, "Rclone command failed: Error listing remotes"
        ):
            self.rclone_handler.list_remotes()
        self.mock_subprocess_run.assert_called_once()

    def test_copy_file_success(self):
        """
        Test copy_file when the rclone command is successful.
        """
        source = "local/path/file.txt"
        destination = "remote:folder/file.txt"
        self.mock_subprocess_run.return_value = MagicMock(
            stdout="Copied file.txt", stderr="", returncode=0
        )
        result = self.rclone_handler.copy_file(source, destination)
        self.assertEqual(result, "Copied file.txt")
        self.mock_subprocess_run.assert_called_once_with(
            ["mock_rclone", "copy", source, destination],
            capture_output=True,
            text=True,
            check=True,
        )

    def test_sync_directory_file_not_found(self):
        """
        Test _execute_rclone_command when rclone executable is not found.
        """
        self.mock_subprocess_run.side_effect = FileNotFoundError
        with self.assertRaisesRegex(RuntimeError, "Rclone not found at mock_rclone"):
            self.rclone_handler.get_version()  # Any command will trigger this

    def test_is_rclone_installed_true(self):
        """
        Test is_rclone_installed when rclone is found.
        """
        self.mock_subprocess_run.return_value = MagicMock(
            stdout="rclone v1.60.0", stderr="", returncode=0
        )
        self.assertTrue(self.rclone_handler.is_rclone_installed())
        self.mock_subprocess_run.assert_called_once_with(
            ["mock_rclone", "version"], capture_output=True, text=True, check=True
        )

    def test_is_rclone_installed_false(self):
        """
        Test is_rclone_installed when rclone is not found or fails.
        """
        self.mock_subprocess_run.side_effect = FileNotFoundError
        self.assertFalse(self.rclone_handler.is_rclone_installed())
        self.mock_subprocess_run.assert_called_once()

    def test_get_version(self):
        """
        Test get_version method.
        """
        self.mock_subprocess_run.return_value = MagicMock(
            stdout="rclone v1.60.0\n", stderr="", returncode=0
        )
        version = self.rclone_handler.get_version()
        self.assertEqual(version, "rclone v1.60.0")
        self.mock_subprocess_run.assert_called_once_with(
            ["mock_rclone", "version"], capture_output=True, text=True, check=True
        )


if __name__ == "__main__":
    unittest.main()
