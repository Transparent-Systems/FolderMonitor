import logging
import sys
import os
import shutil
import subprocess
import time
import yaml
from pathlib import Path

# Add the path to the 'scripts' directory to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from config_models import ConfigModels
from rclone_handler import RcloneHandler
from utils.testing_util import ProcessTestResult
from utils.rclone_util import CheckPath

class DiagnosticUtil:
    """
    Utility class for system diagnostics and configuration checks.
    """

    def __init__(self, logger: logging.Logger | None = None):
        if logger is None:
            test_logger = logging.getLogger("Diagnostic")
            test_logger.setLevel(logging.DEBUG)
            test_logger.propagate = False
            console_handler = logging.StreamHandler()
            formatter = logging.Formatter(
                "%(asctime)s - %(levelname)s - %(name)s - %(message)s"
            )
            console_handler.setFormatter(formatter)
            test_logger.addHandler(console_handler)
            self.logger = test_logger
        else:
            self.logger = logger
        
        self.check_env_result = False
        self.check_config_result = False

    def print_overview(self):
        if (self.check_env_result):
            check_env_result = "OK"
        else:
            check_env_result = "FAILED"
            
        if (self.check_config_result):
            check_config_result = "OK"
        else:
            check_config_result = "FAILED"

        self.logger.info("=== Summary environment and configuration test results BEGIN ===")
        self.logger.info(f"===> Environment test: {check_env_result} <===")
        self.logger.info(f"===> Configuration test: {check_config_result} <==")
        self.logger.info("=== Summary environment and configuration test results END ===")

    def check_env(self, config_path: str) -> bool:
        """
        Checks the environment setup, including Python version, config file, rclone, and dependencies.
        Returns True if all checks pass, False otherwise.
        """
        error_count = 0
        self.logger.debug("--- Folder Monitor: Environment Self-Test ---")
        
        # 1. Check Python Version
        self.logger.debug(f"[*] Python Version: {sys.version.split()[0]} - OK")

        # 2. Check for Config Folder/File
        if os.path.exists(config_path):
            self.logger.debug(f"[*] Config file found: {config_path} - OK")
        else:
            error_count += 1
            self.logger.debug(f"[!] ERROR: Config file NOT found at {config_path}")

        # 3. Check for rclone
        rclone_path = shutil.which("rclone")
        if rclone_path:
            self.logger.debug(f"[*] rclone found at: {rclone_path} - OK")
            try:
                version = subprocess.check_output(["rclone", "version"], text=True).split('\n')[0]
                self.logger.debug(f"    ({version})")
            except Exception:
                self.logger.debug("    [!] Warning: Could not execute rclone version.")
                error_count += 1
        else:
            self.logger.debug("[!] ERROR: 'rclone' not found in system PATH. Please install it from rclone.org.")
            error_count += 1

        # 4. Check for key Python dependencies
        try:
            import pydantic
            import watchdog
            import yaml
            self.logger.debug("[*] Python dependencies (pydantic, watchdog, yaml) - OK")
        except ImportError as e:
            self.logger.debug(f"[!] ERROR: Missing Python dependency: {e}")
            self.logger.debug("    Run 'pip install -r requirements.txt' to fix this.")
            error_count += 1

        self.check_env_result = error_count == 0
        if error_count == 0:
            self.logger.debug("--- Folder Monitor: Environment Self-Test Completed successfully ---")
            return True
        else:
            self.logger.debug(f"--- Folder Monitor: Environment Self-Test - {error_count} tests failed ---")
            return False

    def check_config(self, config_path: str) -> bool:
        """
        Validates the configuration file and runs path checks for each monitor.
        Returns True if configuration is valid and all path checks pass.
        """
        config_models = ConfigModels()
        
        if config_models.validate(config_path=config_path, logger=self.logger):
            self.logger.debug(f"Main - Configuration of {config_path} is valid.")
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

        monitors = monitor_config.get("monitors", [])
        process_test_results: list[ProcessTestResult] = [] 
        
        for monitor in monitors:
            self.logger.debug(f"Processing monitor: {monitor.get('name')}")

            if not monitor.get("enabled"):
                self.logger.debug(f"Monitor {monitor.get('name')} is disabled. Skipping...")
                continue

            monitor_path = monitor.get("monitor_path")
            monitor_name = monitor.get("name")
            destination_path = monitor.get("destination_path")
            testing_config = monitor.get("testing")
            
            if testing_config is None:
                check_delay = 0
            else:
                check_delay = testing_config.get("check-delay", 1)

            process_test_result = self._run_path_check(
                monitor_name=monitor_name,
                source_path=monitor_path,
                destination_path=destination_path,
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
        self.logger.info(f"===> Total counts for all monitors <===")
        self.logger.info("==================================================")
        self.logger.info(f"Total number of tests : {total_success_count + total_failure_count}")
        self.logger.info(f"Total success count   : {total_success_count}")
        self.logger.info(f"Total failure count   : {total_failure_count}")
        self.logger.info(f"Total duration        : {total_duration: .2f} seconds")
        self.logger.info(f"===> End total counts for all monitors <===")

        self.check_config_result = total_failure_count == 0
        return total_failure_count == 0

    def _run_path_check(self, monitor_name: str, source_path: str, destination_path: str, check_delay: int = 1) -> ProcessTestResult:
        """
        Run tests on source and destination paths (Internal helper).
        """
        self.logger.debug("--- Monitor path tests ---")

        # Create rclone_handler to check files at destination_path
        rclone_handler = RcloneHandler(base_destination_path=destination_path, base_source_path=source_path, logger=self.logger, rclone_flags='')
        process_test_result = ProcessTestResult(monitor_name)
        check_path = CheckPath(rclone_handler=rclone_handler, check_delay=check_delay)
        self.logger.debug(f"Starting tests for monitor name [{monitor_name}] on monitor path [{source_path}]...")

        testname = "Test 1 : Check source path exists"
        try:
            #####################################
            
            (found, isdir, files) = check_path.path_exists(path=source_path)
            process_test_result.process(test_case_name=testname, test_ok=found, test_output=files)
            
            #####################################
            testname = "Test 2 : Copy temporary file to destination path"

            # Create a temporary file name using this script name followed by a timestamp
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            # We use 'diagnostic_util' as script name for consistency or generic name
            script_name = "diagnostic_util.py" 
            temp_file_name = f"{script_name}_{timestamp}.txt"
            
            # Create a dummy file content to copy
            # But Rclone copyto expects a local file path.
            # We can create a temp file in the system temp or just use this file.
            
            temp_file_path_local = Path(__file__).resolve()
            
            # The destination path needs to include the filename
            # temp_file_path must be source_path + relative path? 
            # In original script: 
            # temp_file_path = Path(source_path) / temp_file_name
            # destination_path = rclone_handler.get_destination_path(path=temp_file_path)
            # This logic calculates where the file WOULD go if it was in source_path. 
            
            virtual_source_file_path = Path(source_path) / temp_file_name
            destination_file_path = rclone_handler.get_destination_path(path=virtual_source_file_path)
            
            (return_value, result_output) = rclone_handler.run_command(
                ["copyto", temp_file_path_local.as_posix(), destination_file_path]
            )
            output_truncated = result_output[0:100] + " ..." if len(result_output) > 100 else result_output
            process_test_result.process(test_case_name=testname, test_ok=(return_value == 0), test_output=output_truncated)

            #####################################        
            if return_value == 0:
                # Remove temporary file
                (return_value, result_output) = rclone_handler.run_command(
                    ["deletefile", destination_file_path]
                )
                process_test_result.process(test_case_name=f"{testname} - delete temporary file", test_ok=(return_value == 0), test_output=result_output)

        except Exception as e:
            self.logger.debug(f"\n--- Path tests for {monitor_name} FAILED: {e} ---")
            process_test_result.process(test_case_name=testname, test_ok=False ,test_output=f"Fatal error executing tests: {e}")
        finally:
            self.logger.debug(f"\n--- {monitor_name} CLEANUP")

        return process_test_result

    def _log_test_result(self, process_test_result: ProcessTestResult):
        """
        Helper to log the results of a ProcessTestResult.
        """
        self.logger.info(f"===> BEGIN: test results for [{process_test_result.testsuite_name}] <===")
        self.logger.info("==================================================")
        self.logger.info(f"Number of tests : {process_test_result.success_count + process_test_result.failure_count}")
        self.logger.info(f"Success count   : {process_test_result.success_count}")
        self.logger.info(f"Failure count   : {process_test_result.failure_count}")
        self.logger.info(f"Duration        : {process_test_result.duration: .2f} seconds")
        self.logger.info("==================================================")
       
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
                self.logger.info(f"success    | {test_counter:>{max_width}} : {test_full_name}")
                self.logger.info(f"           |      ==> duration: {test_duration: .2f} s")
            else:
                self.logger.info(f"failure    | {test_counter:>{max_width}} : {test_full_name}")
                self.logger.info(f"           |      ==> duration: {test_duration: .2f} s")

                for item in test_result.get("test_output"):
                    self.logger.info(f"           |      {item}")

        self.logger.info(f"===> END: test results for [{process_test_result.testsuite_name}] <===")
