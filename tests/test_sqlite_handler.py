import sys
from pathlib import Path
import argparse
import logging
import unittest

# Add the scripts directory to the Python path
scriptspath = Path(__file__).parent / Path("../scripts")
sys.path.insert(0, scriptspath.resolve().as_posix())

from utils.logging_util import get_unique_logger
from sqlite_handler import SQLiteHandler

class TestSqliteHandler(unittest.TestCase):
    db_path: str
    logger: logging.Logger
    profile_id: int = 0

    @classmethod
    def setUpClass(cls):
        if not cls.db_path:
            raise ValueError("Database path not set for TestSqliteHandler")

        cls.logger.info(f"Using database path: {cls.db_path}")
        cls.sqlite_handler = SQLiteHandler(
            logger=cls.logger,
            db_path=cls.db_path)

    @classmethod
    def tearDownClass(cls):
        cls.sqlite_handler.close()

    def test_01_create_scheme(self):
        try:
            self.sqlite_handler.create_schema()
            self.logger.info("Schema created successfully.")
        except Exception as e:
            self.fail(f"create_schema raised an exception: {e}")

    def test_02_update_schema_version(self):
        try:
            self.sqlite_handler.update_schema_version(version="2.0.0")
            self.logger.info("Scheme version updated successfully.")
        except Exception as e:
            self.fail(f"update_schema_version raised an exception: {e}")

    def test_03_get_current_schema_version(self):
        try:
            current_version = self.sqlite_handler.get_current_schema_version()
            self.logger.info(f"Current scheme version: {current_version}")
        except Exception as e:
            self.fail(f"get_current_schema_version raised an exception: {e}")

    def test_03_01_get_schema_versions(self):
        try:
            schema_versions = self.sqlite_handler.get_schema_versions()
            for schema_version in schema_versions:
                self.logger.info(f"Schema version: {schema_version}")
        except Exception as e:
            self.fail(f"get_current_schema_version raised an exception: {e}")

    def test_04_add_monitor(self):
        try:
            monitor_id = self.sqlite_handler.add_monitor(
                name="test_monitor",
                monitor_path="/tmp/test",
                remote_path="/remote/test",
                monitor_type="periodic_upload",
                config={
                    "monitor_period": "10m",
                    "test": "value"},
                status="active"
            )

            if monitor_id is None:
                self.fail("add_monitor returned None")

            TestSqliteHandler.profile_id = monitor_id
            self.logger.info(f"Monitor added with ID: {monitor_id}")
        except Exception as e:
            self.fail(f"add_monitor raised an exception: {e}")

    def test_05_get_monitor(self):
        try:
            monitor_id = TestSqliteHandler.profile_id
            monitor = self.sqlite_handler.get_monitor(monitor_id)
            self.logger.info(f"Monitor retrieved: {monitor}")

            # Now check the config is correctly deserialized
            config = monitor.get("config", {})
            self.assertIsInstance(config, dict, "config should be a dictionary")
            self.assertEqual(config.get("monitor_period"), "10m", "config monitor_period value mismatch")
            self.assertEqual(config.get("test"), "value", "config test value mismatch")
        except Exception as e:
            self.fail(f"get_monitor raised an exception: {e}")

    def test_06_update_monitor_status(self):
        try:
            monitor_id = TestSqliteHandler.profile_id
            status = "stopped"
            self.sqlite_handler.update_monitor_status(monitor_id, status)
            self.logger.info(f"Monitor status updated to: {status}")
        except Exception as e:
            self.fail(f"update_monitor_status raised an exception: {e}")
    
    def test_07_update_monitor_last_run(self):
        try:
            monitor_id = TestSqliteHandler.profile_id
            last_run = "2023-01-01 00:00:00"
            self.sqlite_handler.update_monitor_last_run(monitor_id, last_run)
            self.logger.info(f"Monitor last run updated to: {last_run}")
        except Exception as e:
            self.fail(f"update_monitor_last_run raised an exception: {e}")

    def test_08_update_monitor_last_heartbeat(self):
        try:
            monitor_id = TestSqliteHandler.profile_id
            last_heartbeat = "2023-01-01 00:00:00"
            self.sqlite_handler.update_monitor_last_heartbeat(monitor_id, last_heartbeat)
            self.logger.info(f"Monitor last heartbeat updated to: {last_heartbeat}")
        except Exception as e:
            self.fail(f"update_monitor_last_heartbeat raised an exception: {e}")

    def test_09_update_monitor_config(self):
        try:
            monitor_id = TestSqliteHandler.profile_id
            config = {"new_config": "value"}
            self.sqlite_handler.update_monitor_config(monitor_id, config)
            self.logger.info(f"Monitor config updated to: {config}")
        except Exception as e:
            self.fail(f"update_monitor_config raised an exception: {e}")


    def test_10_get_all_monitors(self):
        try:
            monitors = self.sqlite_handler.get_monitors()
            self.logger.info(f"All monitors retrieved: {monitors}")
        except Exception as e:
            self.fail(f"get_all_monitors raised an exception: {e}")

    def test_11_delete_monitor(self):
        try:
            monitor_id = TestSqliteHandler.profile_id
            self.sqlite_handler.delete_monitor(monitor_id)
            self.logger.info(f"Monitor deleted with ID: {monitor_id}")
        except Exception as e:
            self.fail(f"delete_monitor raised an exception: {e}")

    def test_20_add_profile(self):
        try:
            profile_id = self.sqlite_handler.add_profile(
                name="test_profile",
                profile_type="aws",
                config={
                    "access_key_id": "AKIA...",
                    "access_key_secret": "SECRET...",
                    "default_region": "us-east-1",
                    "end_point": "my-endpoint"
                }
            )
            self.logger.info(f"Profile added with ID: {profile_id}")
            # Now add a second profile with a complex nested config to test JSON handling
            # For example Google Drive has a token that is a JSON object with nested fields
            complex_config = {
                "handler": "foldermonitor",
                "token": {
                    "access_token": "fake-access-token",
                    "token_type": "Bearer",
                    "refresh_token": "fake-refresh-token",
                    "expiry": "2026-03-03T10:36:59.063709164+13:00"
                },
                "team_drive": {
                    "id": "0Axxxxxx",
                    "name": "My Team Drive"
                }
            }
            complex_profile_id = self.sqlite_handler.add_profile(
                name="complex_profile",
                profile_type="drive",
                config=complex_config
            )
            TestSqliteHandler.profile_id = complex_profile_id if complex_profile_id is not None else 0
            TestSqliteHandler.profile_name = "test_profile"
            self.logger.info(f"Complex profile added with ID: {complex_profile_id}")
        except Exception as e:
            self.fail(f"add_profile raised an exception: {e}")

    def test_21_get_profile_by_id(self):
        try:
            profile_id = TestSqliteHandler.profile_id
            profile = self.sqlite_handler.get_profile(profile_id=profile_id)
            self.logger.info(f"Profile retrieved: {profile}")

            # Now check the config is correctly deserialized
            config = profile.get("config", {})
            self.assertIsInstance(config, dict, "config should be a dictionary")
            self.assertEqual(config.get("handler"), "foldermonitor", "config handler value mismatch")
            token = config.get("token", {})
            self.assertIsInstance(token, dict, "config token should be a dictionary")
            expected_access_token = "fake-access-token"
            access_token = token.get("access_token")
            self.assertEqual(access_token, expected_access_token, "config access_token value mismatch")
        except Exception as e:
            self.fail(f"get_profile_by_id raised an exception: {e}")

    def test_21_get_profile_by_name(self):
        try:
            profile_name = TestSqliteHandler.profile_name
            profile = self.sqlite_handler.get_profile(profile_name=profile_name)
            self.logger.info(f"Profile retrieved: {profile}")

            # Now check the config is correctly deserialized
            config = profile.get("config", {})
            self.assertIsInstance(config, dict, "config should be a dictionary")
        except Exception as e:
            self.fail(f"get_profile_by_name raised an exception: {e}")
            
    def test_22_update_profile(self):
        try:
            profile_id = TestSqliteHandler.profile_id
            self.sqlite_handler.update_profile(
                profile_id=profile_id,
                name="updated_profile",
                profile_type="aws",
                config={
                    "access_key_id": "AKIA_UPDATED...",
                    "access_key_secret": "SECRET_UPDATED...",
                    "default_region": "us-west-2",
                    "end_point": "my-endpoint"
                    }
            
            )
            self.logger.info(f"Profile updated with ID: {profile_id}")
        except Exception as e:
            self.fail(f"update_profile raised an exception: {e}")

    def test_23_get_all_profiles(self):
        try:
            profiles = self.sqlite_handler.get_profiles()
            self.logger.info(f"All profiles retrieved: {profiles}")
        except Exception as e:
            self.fail(f"get_all_profiles raised an exception: {e}")

    def test_24_delete_profile(self):
        try:
            profile_id = TestSqliteHandler.profile_id
            self.sqlite_handler.delete_profile(profile_id)
            self.logger.info(f"Profile deleted with ID: {profile_id}")
        except Exception as e:
            self.fail(f"delete_profile raised an exception: {e}")

    def test_30_get_nonexistent_monitor(self):
        try:
            monitor_id = 9999
            monitor = self.sqlite_handler.get_monitor(monitor_id)
            self.logger.info(f"Non-existent monitor retrieved: {monitor}")
            self.assertEqual(monitor, {}, "Expected empty dict for non-existent monitor")
        except Exception as e:
            self.fail(f"get_monitor raised an exception for non-existent monitor: {e}")

    def test_31_get_nonexistent_profile_id(self):
        try:
            profile_id = 9999
            profile = self.sqlite_handler.get_profile(profile_id)
            self.logger.info(f"Non-existent profile retrieved: {profile}")
            self.assertEqual(profile, {}, "Expected empty dict for non-existent profile")
        except Exception as e:
            self.fail(f"get_profile raised an exception for non-existent profile: {e}")     

    def test_32_update_nonexistent_monitor(self):
        try:
            monitor_id = 9999
            status = "stopped"
            self.sqlite_handler.update_monitor_status(monitor_id, status)
            self.logger.info(f"Attempted to update non-existent monitor with ID: {monitor_id}")
        except Exception as e:
            self.fail(f"update_monitor_status raised an exception for non-existent monitor: {e}")

    def test_33_delete_nonexistent_monitor(self):
        try:
            monitor_id = 9999
            self.sqlite_handler.delete_monitor(monitor_id)
            self.logger.info(f"Attempted to delete non-existent monitor with ID: {monitor_id}")
        except Exception as e:
            self.fail(f"delete_monitor raised an exception for non-existent monitor: {e}")  
    
    def test_34_delete_nonexistent_profile(self):
        try:
            profile_id = 9999
            self.sqlite_handler.delete_profile(profile_id)
            self.logger.info(f"Attempted to delete non-existent profile with ID: {profile_id}")
        except Exception as e:
            self.fail(f"delete_profile raised an exception for non-existent profile: {e}")

    def test_40_map_monitor_to_profile(self):
        # Create monitor and profile first
        try:
            monitor_id = self.sqlite_handler.add_monitor(
                name="test_monitor",
                monitor_path="/tmp/test",
                remote_path="/remote/test",
                monitor_type="instant",
                config={"test": "value"},
                status="active"
            )
            self.logger.info(f"Monitor added with ID: {monitor_id}")
        except Exception as e:
            self.fail(f"add_monitor raised an exception: {e}")

        try:
            profile_id = self.sqlite_handler.add_profile(
                name="test_profile",
                profile_type="aws",
                config={
                    "access_key_id": "AKIA_UPDATED...",
                    "access_key_secret": "SECRET_UPDATED...",
                    "default_region": "us-west-2",
                    "end_point": "my-endpoint"
                    }
            )
            self.logger.info(f"Profile added with ID: {profile_id}")
        except Exception as e:
            self.fail(f"add_profile raised an exception: {e}")

        try:
            if monitor_id is None or profile_id is None:
                self.fail("add_monitor or add_profile returned None")

            self.sqlite_handler.add_monitor_profile_map(monitor_id, profile_id)
            self.logger.info(f"Mapped monitor ID {monitor_id} to profile ID {profile_id}")
        except Exception as e:
            self.fail(f"map_monitor_to_profile raised an exception: {e}")

    def test_41_get_profiles_for_monitor(self):
        try:
            # Get all monitors, select the first one, and get its profiles
            monitors = self.sqlite_handler.get_monitors()
            if not monitors:
                self.fail("No monitors found")
            monitor_id = monitors[0]["id"]
            profiles = self.sqlite_handler.get_profiles_for_monitor(monitor_id)
            self.logger.info(f"Profiles mapped to monitor ID {monitor_id}: {profiles}")
        except Exception as e:
            self.fail(f"get_monitor_profiles raised an exception: {e}")

    def test_42_get_monitors_for_profile(self):
        try:
            # Get all profiles, select the first one, and get its monitors
            profiles = self.sqlite_handler.get_profiles()
            if not profiles:
                self.fail("No profiles found")
            profile_id = profiles[0]["id"]
            monitors = self.sqlite_handler.get_monitors_for_profile(profile_id)
            self.logger.info(f"Monitors mapped to profile ID {profile_id}: {monitors}")
        except Exception as e:
            self.fail(f"get_monitors_for_profile raised an exception: {e}")
            
    def test_43_unmap_monitor_from_profile(self):
        try:
            monitor_id = TestSqliteHandler.profile_id
            profile_id = 1
            self.sqlite_handler.delete_monitor_profile_map(monitor_id, profile_id)
            self.logger.info(f"Unmapped monitor ID {monitor_id} from profile ID {profile_id}")
        except Exception as e:
            self.fail(f"unmap_monitor_from_profile raised an exception: {e}")

    def test_50_add_provider(self):
        try:
            provider_id = self.sqlite_handler.add_provider(
                name="test_provider",
                profile_type="test_type",
                description="test_description",
                config={"test": "value"}
            )

            TestSqliteHandler.profile_id = provider_id if provider_id is not None else 0
            self.logger.info(f"Provider added with ID: {provider_id}")
        except Exception as e:
            self.fail(f"add_provider raised an exception: {e}")

    def test_51_get_provider(self):
        try:
            provider_id = TestSqliteHandler.profile_id # Reusing profile_id variable to store provider_id for testing
            provider = self.sqlite_handler.get_provider(provider_id)
            self.logger.info(f"Provider retrieved: {provider}")
        except Exception as e:
            self.fail(f"get_provider raised an exception: {e}")
    
    def test_52_update_provider(self):
        try:
            provider_id = TestSqliteHandler.profile_id # Reusing profile_id variable to store provider_id for testing
            self.sqlite_handler.update_provider(
                provider_id=provider_id,
                name="updated_provider",
                profile_type="updated_type",
                description="updated_description",
                config={"updated": "value"}
            )
            self.logger.info(f"Provider updated with ID: {provider_id}")
        except Exception as e:
            self.fail(f"update_provider raised an exception: {e}")

    def test_60_lookup_tables(self):

        configs = [
            {
            "monitor-statuses": 
                [
                    {"name": "running", "description": "Monitor is running", "implemented": "true"},
                    {"name": "stop", "description": "Monitor is about to stop", "implemented": "true"},
                    {"name": "stopped", "description": "Monitor has stopped running", "implemented": "true"},
                    {"name": "error", "description": "Monitor has an error state", "implemented": "true"},
                ]
            },
            {
            "monitor-types": 
                [
                    {"name": "instant-upload", "description": "Instant upload to remote", "implemented": "true"},
                    {"name": "periodic_upload", "description": "Periodic upload to remote", "implemented": "true"},
                    {"name": "periodic_download", "description": "Periodic download from remote", "implemented": "true"},
                ]
            },
            {
            "profile-types": 
                [
                    {"name": "s3", "description": "S3 compatible cloud storage, like AWS S2, Cloudflare R2, Backblaze B2 etc", "implemented": "true"},
                    {"name": "drive", "description": "Google Drive", "implemented": "false"},
                    {"name": "azure", "description": "Azure Blob Storage", "implemented": "false"},
                    {"name": "ftp", "description": "FTP Server", "implemented": "false"},
                    {"name" : "sftp", "description": "SFTP Server", "implemented": "false"},
                    {"name" : "ssh", "description": "SSH Server", "implemented": "false"},
                    {"name" : "http", "description": "HTTP Server", "implemented": "false"},
                    {"name" : "https", "description": "HTTPS Server", "implemented": "false"},
                ]
            }
        ]
        try:
            for table_dict in configs:
                for table_name, entries in table_dict.items():
                    self.sqlite_handler.update_lookup_table(table_name, entries)
                    self.logger.info(f"lookup table '{table_name}' populated with {len(entries)} entries")

            self.logger.info("lookup tables added successfully")

            # Now retrieve the lookup tables and check if they are correct
            for table_dict in configs:
                for table_name, entries in table_dict.items():
                    config_list = self.sqlite_handler.get_lookup_table(table_name)
                    # Assert that config_list is equal to entries
                    self.assertEqual(config_list,entries, f"lookup table {table_name} config mismatch")
            
            # Show that lookup table monitor_types
            monitor_types = self.sqlite_handler.get_lookup_table(table_name="monitor_types")
            for monitor_type in monitor_types:
                print(f"Monitor Type: {monitor_type['name']}, Description: {monitor_type['description']}, Implemented: {monitor_type['implemented']}")

        except Exception as e:
            self.fail(f"update_lookup_tables raised an exception: {e}")

    def test_50_cleanup(self):
        try:
            # First delete all monitor-profile mappings
            self.sqlite_handler.cursor.execute("DELETE FROM monitor_profile_map")
            self.sqlite_handler.connection.commit()

            monitors = self.sqlite_handler.get_monitors()
            for monitor in monitors:
                self.sqlite_handler.delete_monitor(monitor["id"])
                self.logger.info(f"Deleted monitor with ID: {monitor['id']}")

            profiles = self.sqlite_handler.get_profiles()
            for profile in profiles:
                self.sqlite_handler.delete_profile(profile["id"])
                self.logger.info(f"Deleted profile with ID: {profile['id']}")

            # Delete lookup tables
            self.sqlite_handler.cursor.execute("DELETE FROM lookup_tables")
            self.sqlite_handler.connection.commit()
            self.logger.info("lookup tables deleted successfully")
        except Exception as e:
            self.fail(f"Cleanup raised an exception: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run integration tests for sqlite_handler using unittest."
    )
    parser.add_argument(
        "-d",
        "--db-path",
        type=str,
        default="tests/data/foldermonitor.sqlite",
        help="Path to database file."
    )
    parser.add_argument(
        "--test-cases",
        type=str,
        nargs="+",
        help="Space-separated list of test method names (or substrings) to run. Leave empty to run all tests."
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="DEBUG",
        help="Log level."
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

    logger = get_unique_logger(args.log_level)
    logger.info("Starting Sqlite Handler Tests")

    # Ensure there is always a schema regardless which test we run
    sqlite_handler = SQLiteHandler(logger=logger, db_path=args.db_path)
    sqlite_handler.create_schema()
    sqlite_handler.close()

    # Inject configuration into Test Class
    TestSqliteHandler.db_path = args.db_path
    TestSqliteHandler.logger = logger

    # Run Tests
    test_loader = unittest.TestLoader()
    full_suite = test_loader.loadTestsFromTestCase(TestSqliteHandler)

    if args.test_cases:
        # Flatten arguments
        patterns = []
        for item in args.test_cases:
            patterns.extend(item.split())

        suite = unittest.TestSuite()
        for test in full_suite:
            if isinstance(test, unittest.TestCase):
                test_method_name = test._testMethodName
                if args.test_cases == [""] or any(pattern in test_method_name for pattern in patterns):
                    suite.addTest(test)
        
        if suite.countTestCases() == 0:
                logger.warning(f"No tests matched patterns: {patterns}")
    else:
        suite = full_suite

    result = unittest.TextTestRunner(verbosity=2).run(suite)

    logger.info("================================")    
    
    if result.wasSuccessful():
        logger.info("All tests passed successfully.")    
    else:
        logger.info("Not all tests passed successfully.")
    logger.info("================================")    
