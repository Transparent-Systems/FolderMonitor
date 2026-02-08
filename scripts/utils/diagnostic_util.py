import importlib
import logging
import sys
import os
import shutil
import subprocess
import time
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

class DiagnosticUtil:
    """
    Utility class for system diagnostics and configuration checks.
    """

    def __init__(self, logger: logging.Logger | None = None):
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
        Check if we can import profiles from rclone
        """
        self.check__profile_import_result = True
        foldermonitor_profile_handler = ProfileHandler(
            logger=self.logger,
            app_name="foldermonitor",
            config_name="foldermonitor.conf"
        )

        rclone_profile_handler = ProfileHandler(
            logger=self.logger,
            app_name="rclone",
            config_name="rclone.conf"
        )

        rclone_profile_names = rclone_profile_handler.get_profile_names()
        if (rclone_profile_names is None or len(rclone_profile_names) == 0):
            print(f"No profiles found in {rclone_profile_handler.config_path}")
            return

        # At present foldermonitor has only native support for S3 type storage
        remote_types_list = ["s3"]
        # Iterate over rlone profile names
        # If a profile is in Rclone but not in foldermonitor, then add profile to profile_to_import list
        # Ask for permissin to import
        # If Yes, then continue
        # If Not, then return
        profiles_to_import = []
        foldermonitor_profile_names = foldermonitor_profile_handler.get_profile_names()
        for profile_name in rclone_profile_names:
            if (profile_name not in foldermonitor_profile_names):
                # Check if the profile has type S3
                profile = rclone_profile_handler.get_profile(profile_name)
                if (profile["type"] in remote_types_list):
                    # Add profile_name to profile list
                    profiles_to_import.append(profile_name)

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

        # Iterate over rlone profile names
        foldermonitor_profile_names = foldermonitor_profile_handler.get_profile_names()
        for profile_name in rclone_profile_names:
            if (profile_name not in foldermonitor_profile_names):
                rclone_profile = rclone_profile_handler.get_profile(profile_name)
                if (rclone_profile["type"] in remote_types_list):
                    # Attributes may differ between providers
                    # For example AWS has no endpoint but a region attribute.
                    # Iterate over keys in rclone profile
                    foldermonitor_profile: dict[str, str] = {}
                    for key in rclone_profile:
                        foldermonitor_profile[key] = rclone_profile[key]

                    if (foldermonitor_profile_handler.add_profile(
                        profile_name=profile_name,
                        profile=foldermonitor_profile)
                        ):
                        print(f"Profile name: {profile_name} imported to foldermonitor profiles")
                    else:
                        print(f"Profile name: {profile_name} not imported to foldermonitor profiles")
        return

    
    def check_app_env(self, config_path: str) -> bool:
        """
        Checks the environment setup, including Python version, config file, and dependencies.
        Returns True if all checks pass, False otherwise.
        """
        error_count = 0
        print("--- Folder Monitor: Environment Self-Test ---")
        
        # Check Python Version
        print(f"[*] Python Version: {sys.version.split()[0]} - OK")

        # Check for Config Folder/File
        if os.path.exists(config_path):
            print(f"[*] Config file found: {config_path} - OK")
        else:
            error_count += 1
            print(f"[!] ERROR: Config file NOT found at {config_path}")

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

    def check_rclone_dependency(self, config_path: str) -> bool:
        """
        Check if there is an Rclone dependency
        There is a dependency if:
            - a profile is referenced in remote_profiles in foldermonitor.yaml
            - that profile is not in foldermonitor conf but is present in rclone conf

        If there is a Rclone dependency, then we check if Rclone is installed.

        The use case that a profile is neither in folder conf and not in rclone conf is handled in check_config()
        """

        # Load configuration from the monitor config file
        try:
            with open(config_path, 'r') as file:
                monitor_config = yaml.safe_load(file)
        except Exception as e:
            self.logger.error(f"Failed to load config file: {e}")
            return False

        monitors = monitor_config.get("monitors", [])

        # Create profile handler for rclone
        rclone_profile_handler = ProfileHandler(
            logger=self.logger,
            app_name="rclone",
            config_name="rclone.conf"
        )

        if (rclone_profile_handler.get_profile_names() is None or len(rclone_profile_handler.get_profile_names()) == 0):
            # No futher checks required
            return True

        foldermonitor_profile_handler = ProfileHandler(
            logger=self.logger,
            app_name="foldermonitor",
            config_name="foldermonitor.conf"
        )

        for monitor in monitors:
            remote_profiles = monitor.get("remote_profiles")
            if not remote_profiles: # None or empty
                continue

            # Iterate over remote_profiles and check if it is only in rclone config
            self.check_rclone_dependency_result = True
            for remote_profile in remote_profiles:
                if foldermonitor_profile_handler.get_profile(profile_name=remote_profile):
                    continue
                if rclone_profile_handler.get_profile(profile_name=remote_profile):
                    # Check if rclone exists
                    if self._check_rclone_exists():
                        self.check_rclone_dependency_result = True
                        return True
                    else:
                        self.check_rclone_dependency_result = False
                        return False
        return True

    def check_app_config(self, config_path: str) -> bool:
        """
        - Validate the configuration file
        - For each monitor test remote_profiles
        - For each monitor print test results
        - Print overview of all test results

        Returns True if configuration is valid and checks for all remote_profile passed.
        """
        config_models = ConfigModels()
        
        if config_models.validate(config_path=config_path, logger=self.logger):
            print(f"Main - Configuration of {config_path} is valid.")
        else:
            self.logger.error(f"Main - Configuration of {config_path} failed.")
            return False

        # Load configuration from the monitor config file
        try:
            with open(config_path, 'r') as file:
                monitor_config = yaml.safe_load(file)
        except Exception as e:
            self.logger.error(f"Failed to load config file: {e}")
            return False

        config_version = monitor_config.get("version")
        print(f"Configuration version: {config_version}")

        monitors = monitor_config.get("monitors", [])
        process_test_results: list[ProcessTestResult] = [] 
        
        for monitor in monitors:
            print(f"Processing monitor: {monitor.get('name')}")
            monitor_path = monitor.get("monitor_path")
            monitor_name = monitor.get("name")
            remote_path = monitor.get("remote_path")
            remote_profiles = monitor.get("remote_profiles")
            testing_config = monitor.get("testing")
            
            if testing_config is None:
                check_delay = 1
            else:
                check_delay = testing_config.get("check-delay", 1)

            process_test_result = self._run_path_checks(
                monitor_name=monitor_name,
                source_path=monitor_path,
                remote_path=remote_path,
                remote_profiles=remote_profiles,
                check_delay=check_delay
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

    def _run_path_checks(self, monitor_name: str, source_path: str, remote_path: str, remote_profiles: list, check_delay: int = 1) -> ProcessTestResult:
        """
        - Check if source path exists
        - Copy temporary file to destination path
        - Delete temporary file from destination path
        """

        process_test_result = ProcessTestResult(monitor_name)
        print(f"Starting tests for monitor name [{monitor_name}] on monitor path [{source_path}]...")
        #####################################
        testname = f"Test source path exists: {source_path}"
        print(testname)
        #####################################
        found = os.path.exists(source_path)
        process_test_result.process(test_case_name=testname, test_ok=found, test_output=f"Source path {source_path} exists: {found}")
        
        #####################################
        # Is remote_path writable ?
        #####################################

        foldermonitor_profile_handler = ProfileHandler(
            logger=self.logger,
            app_name="foldermonitor",
            config_name="foldermonitor.conf"
        )
        foldermonitor_profile_names = foldermonitor_profile_handler.get_profile_names()
        rclone_profile_handler = ProfileHandler(
            logger=self.logger,
            app_name="rclone",
            config_name="rclone.conf"
        )
        rclone_profilenames = rclone_profile_handler.get_profile_names()

        # Create a temporary file name
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        temp_file_name = f"diagnostic_util_test_{timestamp}.txt"
        # Create a local temporary file with dummy content
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix=".txt") as tmp_file:
            tmp_file.write("This is a temporary test file for Folder Monitor diagnostics.")

        # Iterate over remote_profiles
        for remote_profile in remote_profiles:
            #####################################
            testname = f"Test remote_profile: {remote_profile}"
            print(testname)
            #####################################

            # Check if remote_profile is in foldermonitor or rclone conf
            if remote_profile not in foldermonitor_profile_names and remote_profile not in rclone_profilenames:
                process_test_result.process(test_case_name=testname, test_ok=False, test_output=f"Remote profile not found: {remote_profile}")
                continue

            base_handler = BaseHandlerFactory.get_handler(
                logger=self.logger,
                source_path=source_path,
                remote_path=remote_path,
                remote_profile=remote_profile,
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
            self.logger.warning(f"Failed to delete local temp file {temp_file_path}: {e}")

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
            test_case_name = test_result.get("test_case_name")
            test_step_name = test_result.get("test_step_name")
            test_duration = test_result.get("test_duration")
            test_counter = test_result.get("test_counter")

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

                for item in test_result.get("test_output"):
                    print(f"           |      {item}")

        print(f"===> END: test results for [{process_test_result.testsuite_name}] <===")
