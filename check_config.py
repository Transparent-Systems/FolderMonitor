import argparse
import logging
import os
import time
import yaml
import sys
from pathlib import Path

# Add the scripts directory to the Python path
scriptspath = Path(__file__).parent / Path("scripts")
sys.path.insert(0, scriptspath.resolve().as_posix())

from config_models import ConfigModels
from rclone_handler import RcloneHandler
from utils.testing_util import ProcessTestResult
from utils.rclone_util import CheckPath


def run_path_check(monitor_name: str, source_path = "data/Source",destination_path = "data/Destination", logger = None, check_delay=1):
    """
    Run tests on source and destination paths
    """
    logger.debug("--- Monitor path tests ---")

    # Create rclone_handler to check files at destination_path
    rclone_handler = RcloneHandler(base_destination_path=destination_path, base_source_path=source_path, logger=logger, rclone_flags='')
    process_test_result = ProcessTestResult(monitor_name)
    check_path = CheckPath(rclone_handler=rclone_handler, check_delay=check_delay)
    logger.debug(f"Starting tests for monitor name [{monitor_name}] on monitor path [{source_path}]...")

    try:
        #####################################
        testname = "Test 1 : Check source path exists"
        (found, isdir, files) = check_path.path_exists(path=source_path)
        process_test_result.process(test_case_name=testname, test_ok=found, test_output=files)
        
        #####################################
        testname = "Test 2 : Copy temporary file to destination path"

        # Create a temporary file name using this script name followed by a timestamp
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        script_path = os.path.abspath(__file__)
        script_name = os.path.basename(script_path)
        temp_file_name = f"{script_name}_{timestamp}.txt"
        # temp_file_path must be source_path + relative path
        temp_file_path = Path(source_path) / temp_file_name

        destination_path = rclone_handler.get_destination_path(path=temp_file_path)
        (return_value, result_output) = rclone_handler.run_command(
            ["copyto", script_path, destination_path]
            )
        output_truncated = result_output[0:100] + " ..." if len(result_output) > 100 else result_output
        process_test_result.process(test_case_name=testname, test_ok={return_value == 0}, test_output=output_truncated)

        #####################################        
        if return_value == 0:
            # Remove temporary file
            (return_value, result_output) = rclone_handler.run_command(
                ["deletefile", destination_path]
                )
            process_test_result.process(test_case_name=f"{testname} - delete temporary file", test_ok={return_value == 0}, test_output=result_output)

    except Exception as e:
        logger.debug(f"\n--- Path tests for {monitor_name} FAILED: {e} ---")
        process_test_result.process(test_case_name=testname, test_ok=False ,test_output=f"Fatal error executing tests: {e}")
    finally:
        logger.debug(f"\n--- {monitor_name} CLEANUP")

    return process_test_result


"""
    Check the configuration YAML file.
    By default this is conf/config.yaml.
    The path to the config file can eb changed with the --config-path argument.
    Call example:
        python check_config.py --config-path conf/config.yaml
"""
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG, format='%(levelname)s: %(message)s')
    logger = logging.getLogger(__name__)
    parser = argparse.ArgumentParser(description="Load and validate a configuration file.")
    parser.add_argument("--config-path", 
                        default="conf/config.yaml", 
                        type=str, 
                        help="The path to the configuration file."
                        )
    args = parser.parse_args()
   
    config_models = ConfigModels()
    config_path = args.config_path
    if (config_models.validate(config_path=config_path, logger=logger)):
        logger.debug(f"Main - Configuration of {config_path} is valid.")
    else:
        logger.error(f"Main - Configuration of {config_path} failed.")
        sys.exit(1)

    # Load configuration from the monitor config file
    with open(args.config_path, 'r') as file:
        monitor_config = yaml.safe_load(file)

    monitors = monitor_config.get("monitors")

    # Iterate over monitors, creating a MonitorHandler for each one and starting it
    monitor_handlers = set()
    process_test_results : list[ProcessTestResult] = [] 
    for monitor in monitors:
        logger.debug(f"Processing monitor: {monitor['name']}")

        if not monitor.get("enabled"):
            logger.debug(f"Monitor {monitor['name']} is disabled. Skipping...")
            continue

        monitor_path = monitor.get("monitor_path")
        monitor_name = monitor.get("name")
        destination_path = monitor.get("destination_path")
        testing_config = monitor.get("testing")
        if testing_config is None:
            check_delay =0
        else:
            check_delay = testing_config.get("check-delay", 1)

        process_test_result = run_path_check(
            monitor_name=monitor_name,
            source_path=monitor_path,
            destination_path=destination_path,
            logger=logger, 
            check_delay=check_delay
            )
        process_test_results.append(process_test_result)

    # Print test resuls of all monitors
    total_success_count = 0
    total_failure_count = 0
    total_duration = 0
    for process_test_result in process_test_results:
        total_success_count += process_test_result.success_count
        total_failure_count += process_test_result.failure_count
        total_duration += process_test_result.duration
        logger.info(f"===> BEGIN: test results for [{process_test_result.testsuite_name}] <===")
        logger.info("==================================================")
        logger.info(f"Number of tests : {process_test_result.success_count + process_test_result.failure_count}")
        logger.info(f"Success count   : {process_test_result.success_count}")
        logger.info(f"Failure count   : {process_test_result.failure_count}")
        logger.info(f"Duration        : {process_test_result.duration: .2f} seconds")
        logger.info("==================================================")
       
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
                logger.info(f"success    | {test_counter:>{max_width}} : {test_full_name}")
                logger.info(f"           |      ==> duration: {test_duration: .2f} s")
            else:
                logger.info(f"failure    | {test_counter:>{max_width}} : {test_full_name}")
                logger.info(f"           |      ==> duration: {test_duration: .2f} s")

                for item in test_result.get("test_output"):
                    logger.info(f"           |      {item}")

        logger.info(f"===> END: test results for [{process_test_result.testsuite_name}] <===")

    # Print totals over all monitors
    logger.info(f"===> Total counts for all monitors <===")
    logger.info("==================================================")
    logger.info(f"Total number of tests : {total_success_count + total_failure_count}")
    logger.info(f"Total success count   : {total_success_count}")
    logger.info(f"Total failure count   : {total_failure_count}")
    logger.info(f"Total duration        : {total_duration: .2f} seconds")
    logger.info(f"===> End total counts for all monitors <===")
