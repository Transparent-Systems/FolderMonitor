import os
import sys
import logging

# Add the scripts directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../scripts')))

from rclone_handler import RcloneHandler

def run_integration_check(destination_path = "data/Destination", base_path = "", logger = None, rclone_flags = ""):
    logger.debug("--- Rclone Integration Check ---")
    handler = RcloneHandler(destination_path, base_path, logger, rclone_flags)
    test_remote = "e2" # CHANGE THIS TO YOUR ACTUAL TEST REMOTE

    try:
        # Test 1: Get Version
        logger.debug("\n1. Getting Rclone Version...")
        (result_code, result_output) = handler.get_rclone_version()
        logger.debug(f"Rclone Version: {result_output}")
        assert "rclone" in result_output.lower()

        # Test 2: List Remotes
        logger.debug("\n2. Listing Remotes...")
        (result_code, result_output) = handler.list_remotes()
        logger.debug(f"Configured Remotes:\n{result_output}")
        assert f"{test_remote}:" in result_output

    #     # Test 3: Copy a test file to a temporary location on the remote
    #     logger.debug(f"\n3. Copying a test file to '{test_remote}'...")
    #     temp_dir = "integration_test_temp"
    #     local_file_path = "local_test_file.txt"
    #     remote_file_path = f"{test_remote}:{temp_dir}/test_copy.txt"

    #     # Create a local dummy file
    #     with open(local_file_path, "w") as f:
    #         f.write("Hello from integration test!")

    #     handler.copy_file(local_file_path, remote_file_path)
    #     logger.debug(f"Copied '{local_file_path}' to '{remote_file_path}'")

    #     # Verify file existence on remote (using lsf)
    #     logger.debug("Verifying file on remote...")
    #     remote_ls_output = handler._execute_rclone_command(["lsf", f"{test_remote}:{temp_dir}/"])
    #     logger.debug(f"Remote content:\n{remote_ls_output}")
    #     assert "test_copy.txt" in remote_ls_output

    #     # Clean up the remote test directory
    #     logger.debug(f"\n4. Cleaning up remote test directory '{test_remote}:{temp_dir}'...")
    #     handler._execute_rclone_command(["purge", f"{test_remote}:{temp_dir}"])
    #     logger.debug("Remote directory purged.")

    #     # Verify remote is empty
    #     remote_ls_after_purge = handler._execute_rclone_command(["lsf", f"{test_remote}:{temp_dir}/"])
    #     assert "test_copy.txt" not in remote_ls_after_purge # Should be empty
    #     logger.debug("Remote directory verified empty.")


    #     logger.debug("\n--- All integration checks passed! ---")

    except Exception as e:
        logger.debug(f"\n--- Integration check FAILED: {e} ---")
    finally:
        logger.debug(f"\n--- Integration check cleanup")
        # if os.path.exists(local_file_path):
        #     os.remove(local_file_path)



def create_test_data(path: str, file_list: list[str]):
    os.makedirs(path, exist_ok=True)
    for filename in file_list:
        file_path = os.path.join(path, filename)
        head = os.path.dirname(file_path)
        os.makedirs(head, exist_ok=True)

        with open(file_path, 'w') as f:
            logger.debug(f"Writing to file {filename}")
            f.write(f"Test data for {filename}\n")

   
if __name__ == "__main__":
    if len(sys.argv) < 2:
        path = "data"
    else:
        path = sys.argv[1]

    test_files = []
    test_files.append("Source/Cloud/Test1/test1.txt")
    test_files.append("Source/Cloud/Test1/test2.txt")
    test_files.append("Source/Cloud/Test1/Subfolder1/test1.txt")
    test_files.append("Source/Cloud/Test1/Subfolder1/test2.txt")
    test_files.append("Source/Cloud/Test1/Subfolder2/test1.txt")
    test_files.append("Source/Cloud/Test1/Subfolder2/test2.txt")
    test_files.append("Source/Cloud/Test2/test1.txt")
    test_files.append("Source/Cloud/Test2/test2.txt")
    test_files.append("Source/Cloud/Test2/Subfolder1/test1.txt")
    test_files.append("Source/Cloud/Test2/Subfolder1/test2.txt")
    test_files.append("Source/Cloud/Test2/Subfolder2/test1.txt")
    test_files.append("Source/Cloud/Test2/Subfolder3/test2.txt")
    # create_test_data(path, test_files)

    destination_path = "data/Destination"
    base_path = "Cloud"
    rclone_flags = ""

    # Setup logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG) # Set the overall minimum logging level
    # Remove default handlers if any (crucial for clean setup)
    for h in root_logger.handlers[:]:
        root_logger.removeHandler(h)

    console_handler_real = logging.StreamHandler()

    formatter = logging.Formatter(
        "%(asctime)s - %(levelname)s - %(name)s - %(message)s"
    )
    console_handler_real.setFormatter(formatter)
    root_logger.addHandler(console_handler_real)
    root_logger.debug("Root logger configured with queue handler.")
    # --- End Central Logging Setup ---

    # # Get a unique logger instance
    # logger = get_unique_logger(log_config)
 
    logger = logging.getLogger()
    logger.debug("Before calling run_integration_check")
    run_integration_check(destination_path, base_path, logger, rclone_flags)

