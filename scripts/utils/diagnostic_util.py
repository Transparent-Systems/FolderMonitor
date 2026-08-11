import importlib.util
import logging
import sys
import os
import shutil
import subprocess
import time
from typing import Any, Self
import yaml
import tempfile
from pathlib import Path

root_folder = os.path.join(os.path.dirname(__file__), '../..')
root_folder_abs = os.path.abspath(root_folder)
if root_folder_abs not in sys.path:
    sys.path.append(root_folder_abs)

from scripts.base_handler_factory import BaseHandlerFactory
from scripts.profile_handler import ProfileHandler
from scripts.config_models import ConfigModels
from scripts.utils.testing_util import ProcessTestResult
from scripts.sqlite_handler import SQLiteHandler

class DiagnosticUtil:
    """
    Utility class for system diagnostics and configuration checks.
    """

    def __init__(self, db_path: str, logger: logging.Logger | None = None):
        if logger is None:
            test_logger = logging.getLogger(__name__)
            test_logger.setLevel(logging.DEBUG)
            console_handler = logging.StreamHandler()
            formatter = logging.Formatter(
                "%(asctime)s - %(levelname)s - %(name)s - %(message)s"
            )
            console_handler.setFormatter(formatter)
            test_logger.addHandler(console_handler)
            self.logger = test_logger
        else:
            self.logger = logger
        
        self.check_app_env_result = False
        self.check__profile_import_result = False
        self.check_rclone_dependency_result = False
        self.check_app_config_result = False
        self.sqlite_handler = SQLiteHandler(
                logger=self.logger,
                db_path=db_path
        )

    def print_overview(self):
        print("=" *50)
        print("=== Summary environment and configuration test results BEGIN ===")
        print(f"===> App environment test: {"OK" if self.check_app_env_result else "FAILED"} <===")
        print(f"===> Check import remote profiles: {"OK" if self.check__profile_import_result else "FAILED"} <===")
        print(f"===> Check rclone dependency: {"OK" if self.check_rclone_dependency_result else "FAILED"} <===")
        print(f"===> App configuration test: {"OK" if self.check_app_config_result else "FAILED"} <==")
        print("=== Summary environment and configuration test results END ===")


    def check_profile_import(self):
        """
        Check if we can import profiles from rclone.
        Only import profiles not yet present in profiles table
        """
        self.check__profile_import_result = True

        rclone_profile_handler = ProfileHandler(
            logger=self.logger,
            app_name="rclone",
            config_name="rclone.conf"
        )

        rclone_profile_names = rclone_profile_handler.get_profile_names()
        if (rclone_profile_names is None or len(rclone_profile_names) == 0):
            print(f"No profiles found in {rclone_profile_handler.config_path}")
            return

        # In release 3 we import profiles regardless of profile_type.
        # That way a monitor can be linked to a profile that has been imported
        # Imported profile_types are marked with "implemented = false"
        implemented_profiles = self.sqlite_handler.get_implemented_profiles()
        if not implemented_profiles:
            print(f"No implemented profiles found in {self.sqlite_handler.db_path}")
            return

        implemented_profile_types = []
        for implemented_profile in implemented_profiles:
            profile_type = implemented_profile.get("name", "")
            implemented_profile_types.append(profile_type)

        # Iterate over rlone profile names
        # If a profile is in Rclone but not in foldermonitor, then add profile to profile_to_import list
        # Ask for permissin to import
        # If Yes, then continue
        # If Not, then return
        profiles_to_import = []
        foldermonitor_profile_names = []
        profiles = self.sqlite_handler.get_profiles()
        if profiles:
            for profile in profiles:
                profile_name = profile.get("name", "")
                foldermonitor_profile_names.append(profile_name)

        for rclone_profile_name in rclone_profile_names:
            if rclone_profile_name in foldermonitor_profile_names:
                continue
            profiles_to_import.append(rclone_profile_name)

        if (len(profiles_to_import) == 0):
            print("No profiles to import")
            return

        # Prompt user for permission to import profiles
        print("\n")
        print("=" *60)
        print("Please confirm to import the following profiles from Rclone")
        print("This increases performance and reduces dependencies")
        print("The profiles are:")
        i = 0
        for profile_name in profiles_to_import:
            i += 1
            print(f"{i}. {profile_name}")

        print("Ok to import profiles? (y/n)")
        print("Y: Yes is default value, press Enter to accept")
        print("N: No")
        import_ok = input("Press Enter key to accept default value: Yes\n")
        if (import_ok.strip() != "" and import_ok.lower() != "y"):
            print("Profile import cancelled")
            return

        # Some Rclone attribute names differ from those in FolderMonitor
        # We use a map to conver those attribute names
        config_attribute_map = {
            "provider": "provider_name",
            "access_key_secret" : "access_key_secret"
        }

        existing_profile_names = []
        profiles = self.sqlite_handler.get_profiles()
        for profile in profiles:
            profile_name = profile.get("name", "")
            existing_profile_names.append(profile_name)

        config_attribute_map_keys = config_attribute_map.keys()
        # Iterate over rlone profile names
        for profile_name in rclone_profile_names:
            # If the profile already exists, then skip it
            if profile_name in existing_profile_names:
                continue

            rclone_profile = rclone_profile_handler.get_profile(profile_name)
            profile_type = ""
            profile_config = {}
            # Store each attribute with their corresponding name in profile_config
            for key in rclone_profile:
                if key == "type":
                    profile_type = rclone_profile[key]
                elif key in config_attribute_map_keys:
                    profile_config[config_attribute_map[key]] = rclone_profile[key]
                else:
                    profile_config[key] = rclone_profile[key]

            # If provider_name present, but provider_id not present then lookup the provider
            if "provider_name" in profile_config.keys():
                if not "provider_id" in profile_config.keys():
                    provider = self.sqlite_handler.get_provider(
                        provider_name=profile_config["provider_name"]
                    )
                    if provider:
                        profile_config["provider_id"] = provider["id"]
                    else:
                        # Add provider
                        provider_name = profile_config["provider_name"]
                        print(f"Adding provider: {provider_name}")
                        provider_config = {}
                        provider_config["imported"] = "true"
                        if self.sqlite_handler.add_provider(
                            name=provider_name,
                            profile_type=profile_type,
                            description=provider_name,
                            config=provider_config
                        ):
                            self.logger.info(f"Added provider: {provider_name}")
                            provider = self.sqlite_handler.get_provider(provider_name=provider_name)
                            profile_config["provider_id"] = provider["id"]
                            profile_config["provider_name"] = provider["name"]
                        else:
                           self.logger.warning(f"Failed to add provider: {profile_config['provider_name']}") 

            # Add profile to database
            if self.sqlite_handler.add_profile(
                name=profile_name,
                profile_type=profile_type,
                config=profile_config
            ):
                print(f"Profile name: {profile_name} imported to profiles")
            else:
                print(f"Profile name: {profile_name} not imported to profiles")
        
        return

    
    def check_app_env(self) -> bool:
        """
        Checks the environment setup, including Python version, and dependencies.
        Returns True if all checks pass, False otherwise.
        """
        error_count = 0
        print("--- Folder Monitor: Environment Self-Test ---")
        
        # Check Python Version
        print(f"[*] Python Version: {sys.version.split()[0]} - OK")

        # Check for key Python dependencies
        packages = ["pydantic", "watchdog", "yaml", "boto3"]
        missing = []

        for pkg in packages:
            # find_spec returns None if the package isn't installed
            if importlib.util.find_spec(pkg) is None:
                missing.append(pkg)
        
        if missing:
            print(f"[!] ERROR: Missing Python dependency: {', '.join(packages)}")
            print("    Run 'pip install -r requirements.txt' to fix this.")
            error_count += 1
        else:
            print(f"[*] Python dependencies ({', '.join(packages)}) - OK")

        self.check_app_env_result = error_count == 0
        if error_count == 0:
            print("--- Folder Monitor: App Environment Self-Test Completed successfully ---")
        else:
            print(f"--- Folder Monitor: App Environment Self-Test - {error_count} tests failed ---")

        return error_count == 0

    def _check_rclone_exists(self) -> bool:
        """
        Check if Rclone exists and we can get the version
        """

        # Check rclone
        rclone_path = shutil.which("rclone")
        if rclone_path:
            print(f"[*] rclone found at: {rclone_path} - OK")
            try:
                version = subprocess.check_output(["rclone", "version"], text=True).split('\n')[0]
                print(f"    ({version})")
                return True
            except Exception:
                print("    [!] Warning: Could not execute rclone version.")
                return False
        else:
            print("[!] ERROR: 'rclone' not found in system PATH. Please install it from rclone.org.")
            return False

    def check_rclone_dependency(self) -> bool:
        """
        Check if there is an Rclone dependency
        There is a dependency if:
            - a profile is referenced in remote_profiles in foldermonitor.yaml
            - that profile is not in foldermonitor conf but is present in rclone conf

        If there is a Rclone dependency, then we check if Rclone is installed.

        The use case that a profile is neither in folder conf and not in rclone conf is handled in check_config()
        """

        # Get all monitors using SQLiteHandler
        monitors = self.sqlite_handler.get_monitors()
        if monitors is None:
            self.logger.error("Failed to get monitors from database")
            return True

        # All profiles in remote_profiles should be in foldermonitor.sqlite database now, because:
        # - We either have imported the rclone profiles
        # - Or we have created the profiles manually
        # sqlite_handler has a metthod to get all profiles for a monitor

        profiles = self.sqlite_handler.get_profiles()
        if profiles is None:
            self.logger.error("Failed to get profiles from database")
            return True

        # Iterate over profiles, check if a profile has rclone handler, then check if reclone is installed once only
        # The handler is a key in config dictionary
        for profile in profiles:
            profile_name = profile.get("name")
            if profile_name is None:
                continue
            config = profile.get("config", {})
            handler = config.get("handler")
            if handler is None:
                continue
            if handler == "foldermonitor":
                continue
            if handler == "rclone":
                # Check to see if rclone is installed, if not then we have a dependency problem
                if self._check_rclone_exists():
                    self.check_rclone_dependency_result = True
                    break;
                else:
                    self.check_rclone_dependency_result = False
                    self.logger.error("Rclone is not installed but is required by a profile.")
                    return False

        return True

    def check_monitor_config(self, monitor_id: int) -> bool:
        """
        Check if monitor config is valid
        """


        return True
 
    def check_monitor_config(self, monitor_id: int | None = None) -> bool:
        """
        - For each monitor test remote_profiles
        - For each monitor print test results
        - Print overview of all test results

        Returns True if checks for all profiles passed.
        """

        # Get all monitors using SQLiteHandler
        monitors = self.sqlite_handler.get_monitors()
        if monitors is None:
            self.logger.error("Failed to get monitors from database")
            return False

        process_test_results : list[ProcessTestResult] = []
        for monitor in monitors:
            if monitor_id is not None and monitor.get("id") != monitor_id:
                continue

            print(f"Processing monitor: {monitor.get('name')}")
            monitor_id : int = monitor.get("id", 0)

            if not monitor_id:
                self.logger.error("Monitor ID is missing or invalid for monitor: %s", monitor_id)
                continue
            
            monitor_name = monitor.get("name", "")
            monitor_path = monitor.get("monitor_path"   , "")
            remote_path = monitor.get("remote_path", "")

            # Get profiles for this monitor using sqlite_handler
            profiles = self.sqlite_handler.get_profiles_for_monitor(
                monitor_id=monitor_id
            )
            if profiles is None:
                self.logger.error("Failed to get profiles for monitor_id: %s", monitor_id)
                continue

            # Get testing_delay
            testing_delay = 1
            config = monitor.get("config", {})
            if config:
                if "testing_delay" in config.keys():
                    testing_delay = config.get("testing_delay", 1)
                else:   
                    testing_delay = 1

            process_test_result = self._run_path_checks(
                monitor=monitor,
                check_delay=testing_delay
            )
            process_test_results.append(process_test_result)

        # Print test results of all monitors
        total_success_count = 0
        total_failure_count = 0
        total_duration = 0
        
        for process_test_result in process_test_results:
            total_success_count += process_test_result.success_count
            total_failure_count += process_test_result.failure_count
            total_duration += process_test_result.duration
            self._log_test_result(process_test_result)

        # Print totals over all monitors
        print("===> Total counts for all monitors <===")
        print("==================================================")
        print(f"Total number of tests : {total_success_count + total_failure_count}")
        print(f"Total success count   : {total_success_count}")
        print(f"Total failure count   : {total_failure_count}")
        print(f"Total duration        : {total_duration: .2f} seconds")
        print("===> End total counts for all monitors <===")

        self.check_app_config_result = total_failure_count == 0
        return total_failure_count == 0

    def _run_path_checks(self, monitor: dict[str, Any], check_delay: int = 1) -> ProcessTestResult:
        """
        - Check if source path exists
        - Copy temporary file to destination path
        - Delete temporary file from destination path
        """

        process_test_result = ProcessTestResult()
        print(f"Starting tests for monitor name [{monitor.get('name', '')}] on monitor path [{monitor.get('monitor_path', '')}]...")
        #####################################

        testname = f"Test source path exists: {monitor_path}"
        print(testname)
        #####################################
        monitor_id = monitor.get("id", 0)
        monitor_path = monitor.get("monitor_path", "")
        remote_path = monitor.get("remote_path", "")
        found = os.path.exists(monitor_path)
        process_test_result.process(test_case_name=testname, test_ok=found, test_output=f"Source path {monitor_path} exists: {found}")
        
        #####################################
        # Is remote_path writable ?
        #####################################

        # Create a temporary file name
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        temp_file_name = f"diagnostic_util_test_{timestamp}.txt"
        # Create a local temporary file with dummy content
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix=".txt") as tmp_file:
            tmp_file.write("This is a temporary test file for Folder Monitor diagnostics.")

        # Iterate over remote_profiles of this monitor
        profiles = self.sqlite_handler.get_profiles_for_monitor(
            monitor_id=monitor_id
            )

        for profile in profiles:
            #####################################
            profile_name = profile.get("name", "")
            testname = f"Test remote_profile: {profile_name}"
            print(testname)
            #####################################

            remote_profile = profile.get("name", "")
            base_handler = BaseHandlerFactory.get_handler(
                logger=self.logger,
                source_path=monitor_path,
                remote_path=remote_path,
                profile_type=remote_profile,
            )

            if base_handler is None:
                process_test_result.process(test_case_name=testname, test_ok=False, test_output=f"Could not get base_handler for remote_profile: {remote_profile}")
                continue

            
            source_path_file = str(Path(tmp_file.name).resolve())
            print(f"source_path_file: {source_path_file}")            
            remote_path_file = f"{remote_path}/{temp_file_name}"
            print(f"remote_path_file: {remote_path_file}")
            
            result_code, result_output = base_handler.copy_file(
                source_path=source_path_file, 
                remote_path=remote_path_file
                )
            process_test_result.process(test_case_name=testname, test_ok=(result_code == 0), test_output=f"Result of copy: {result_code}")

            # Wait 
            time.sleep(check_delay)
            result_code, result_output = base_handler.delete_file(
                remote_path=remote_path_file
                )
            process_test_result.process(test_case_name=testname, test_ok=(result_code == 0), test_output=f"Result of delete: {result_code}")

        # Delete local temporary file
        try:
            # Convert str to Path
            temp_file_path = Path(tmp_file.name)
            if temp_file_path.exists():
                os.unlink(temp_file_path)
        except Exception as e:

            self.logger.warning(f"Failed to delete local temp file {temp_file_name}: {e}")

        return process_test_result


    def _log_test_result(self, process_test_result: ProcessTestResult):
        """
        Helper to log the results of a ProcessTestResult.
        """
        print(f"===> BEGIN: test results for [{process_test_result.testsuite_name}] <===")
        print("==================================================")
        print(f"Number of tests : {process_test_result.success_count + process_test_result.failure_count}")
        print(f"Success count   : {process_test_result.success_count}")
        print(f"Failure count   : {process_test_result.failure_count}")
        print(f"Duration        : {process_test_result.duration: .2f} seconds")
        print("==================================================")
       
        len_test_results = len(process_test_result.test_results)
        max_width = len(str(len_test_results))
        for test_result in process_test_result.test_results:
            test_case_name = test_result.get("test_case_name", "")
            test_step_name = test_result.get("test_step_name", "")
            test_duration = test_result.get("test_duration", 0.0)
            test_counter = test_result.get("test_counter", 0)

            if len(test_step_name) == 0:        
                test_full_name = test_case_name
            else:
                test_full_name = f"{test_case_name} - {test_step_name}"
            
            if test_result.get("test_ok"):
                print(f"success    | {test_counter:>{max_width}} : {test_full_name}")
                print(f"           |      ==> duration: {test_duration: .2f} s")
            else:
                print(f"failure    | {test_counter:>{max_width}} : {test_full_name}")
                print(f"           |      ==> duration: {test_duration: .2f} s")

                for item in test_result.get("test_output", []):
                    print(f"           |      {item}")

        print(f"===> END: test results for [{process_test_result.testsuite_name}] <===")
