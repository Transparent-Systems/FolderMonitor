# Add the scripts directory to the Python path

import os
import sys
from pathlib import Path
import logging
from dotenv import load_dotenv

scripts_path = Path(__file__).parent / Path("../scripts")
if not scripts_path in sys.path:
    sys.path.insert(0, scripts_path.resolve().as_posix())

from sqlite_handler import SQLiteHandler


class DatabaseTestData:

    def __init__(self, logger: logging.Logger, db_path: str, dotenv_path: str):
        self.dotenv_path = dotenv_path
        self.logger = logger
        self.sqlite_handler: SQLiteHandler = SQLiteHandler(
            logger=logger,
            db_path=db_path
        )

        self.sqlite_handler.create_schema()
        self.sqlite_handler.load_support_tables()


    def load_test_data(self):
        """
        Add test data to SQLite database
        """

        self.logger.info("Loading test data")
        self.logger.info(f"dotenv_path: {self.dotenv_path}")

        load_dotenv(self.dotenv_path)

        # Set schema version
        self.sqlite_handler.update_schema_version(version="1.0.0")

        # Lookup id of provider "Idrive E2"
        provider_name = "IDrive"
        provider = self.sqlite_handler.get_provider(
            provider_name=provider_name
        )
        provider_id = provider.get("id")
        self.logger.debug(f"Provider {provider_name} id: {provider_id}")

        # Add profiles to database
        test_profiles = [
            {
                "name": "s3-test",
                "type": "s3",
                "config": {
                    "provider_id" : f"{provider_id}",
                    "provider_name" : "IDrive",
                    "access_key_id" : "${S3_TEST_ACCESS_KEY_ID}",
                    "access_key_secret" : "${S3_TEST_ACCESS_KEY_SECRET}",
                    "endpoint" : "${S3_TEST_ENDPOINT}"
                    }
            },
            {
                "name": "s3-test-2",
                "type": "s3",
                "config": {
                    "provider_id" : f"{provider_id}",
                    "provider_name" : "IDrive",
                    "access_key_id" : "${S3_TEST_ACCESS_KEY_ID}",
                    "access_key_secret" : "${S3_TEST_ACCESS_KEY_SECRET}",
                    "endpoint" : "${S3_TEST_ENDPOINT}"
                    }
            },
            {
                "name": "rclone-test",
                "type": "ftp",
                "config": {
                    "pass": "${RCLONE_TEST_FTP_PASS}",
                    "comment": "Credentials stored here are for informational purposes only."
                }
            }
        ]

        # Replace credentials with values from the environment
        profile_config_keys = ["access_key_id", "access_key_secret", "endpoint", "pass"]
        # Iterate over each key in test_profile and replace variable
        for profile in test_profiles:
            self.logger.debug(f"Replacing vars in profile: {profile['name']}")
            profile_config = profile.get("config")
            if profile_config is None:
                continue
            for profile_config_key in profile_config:
                if profile_config_key not in profile_config_keys:
                    continue
                profile_config_value = profile_config.get(profile_config_key) or ""
                if not isinstance(profile_config_value, str):
                    continue
                # Replace with env var
                for env_key in os.environ:
                    env_value = os.environ.get(env_key)
                    if env_value is None:
                        continue
                    # var_key = f"${{env_key}}"
                    var_key = "${" + env_key + "}"
                    if var_key in profile_config_value:
                        new_value = profile_config_value.replace(var_key, env_value)
                        profile_config[profile_config_key] = new_value
            self.logger.debug(f"Profile: {profile}")

        # Add profiles to database
        for profile in test_profiles:
            self.logger.debug(f"Adding profile: {profile['name']}")
            # Add profile to database
            self.sqlite_handler.add_profile(
                name=profile["name"],
                profile_type=profile["type"],
                config=profile["config"]
            )

        # Create monitors
        test_monitors = [
            {
                "name": "Test Monitor 1",
                "monitor_path": "testdata/source/monitor",
                "remote_path" : "test-foldermonitor",
                "monitor_type": "instant-upload",
                "config" : {},
                "status": "stopped"
            },
            {
                "name": "Test Monitor 2",
                "monitor_path": "testdata/source/monitor",
                "remote_path" : "test-foldermonitor",
                "monitor_type": "periodic_upload",
                "config" : {"period": "10m"},
                "status": "stopped"
            }
        ]

        for monitor in test_monitors:
            self.logger.debug(f"Adding monitor: {monitor['name']}")
            # Add monitor to database
            self.sqlite_handler.add_monitor(
                name=monitor["name"],
                monitor_path=monitor["monitor_path"],
                remote_path=monitor["remote_path"],
                monitor_type=monitor["monitor_type"],
                config=monitor["config"],
                status=monitor["status"]
            )

        monitors = self.sqlite_handler.get_monitors()
        profiles = self.sqlite_handler.get_profiles()

        # Link monitors to all profiles
        for monitor in monitors:
            for profile in profiles:
                self.sqlite_handler.add_monitor_profile_map(monitor_id=monitor["id"], profile_id=profile["id"])
        
        self.logger.info(f"Loading test data completed")



    def remove_test_data(self):
        """
        Remove test data from SQLite database
        Do not wipe out support tables like provider and (virtual) lookup_tables
        """

        self.logger.info("Removing test data")
        # Check if database connection is open before attempting to clean up
        try:
            if self.sqlite_handler.connection is None:
                self.logger.warning("SQLite connection is already closed. Skipping cleanup.")
                return
            
            monitors = self.sqlite_handler.get_monitors()
            for monitor in monitors:
                monitor_id = monitor["id"]
                # Now delete this monitor
                self.sqlite_handler.delete_monitor(monitor_id=monitor_id)

            # Delete all profiles
            profiles = self.sqlite_handler.get_profiles()
            for profile in profiles:
                self.sqlite_handler.delete_profile(profile["id"])

        except Exception as e:
            self.logger.error(f"Error during teardown: {e}")
        finally:    
            self.logger.info(f"Cleanup database completed")

if __name__ == "__main__":
    logger = logging.getLogger()
    console_handler = logging.StreamHandler()
    formatter = logging.Formatter(
        "%(asctime)s - %(levelname)s - %(name)s - %(message)s"
    )
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.DEBUG)
    logger.setLevel(logging.DEBUG)
    logger.addHandler(console_handler)
    db_path = "tests/data/foldermonitor.sqlite"
    dotenv_path = "tests/data/.env"
    database_test_data = DatabaseTestData(
        logger=logger,
        db_path=db_path,
        dotenv_path=dotenv_path
    )

    database_test_data.load_test_data()
