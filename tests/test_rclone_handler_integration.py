import os
import sys
import logging
import shutil

# Add the scripts directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../scripts')))

from rclone_handler import RcloneHandler

def get_destination_path(path, base_path, root_destination_path):
    path = path.replace("\\", "/")
    # Return part after base_path
    # Or entire path if base_path not found
    try:
        index = path.index(base_path)
        return_path = path[index + len(base_path):]
    except ValueError:
        return_path = path

    if return_path.startswith("/"):
        return f"{root_destination_path}{return_path}"
    else:
        return f"{root_destination_path}/{return_path}"


def run_integration_check(src_path = "data/Source/test_rclone_handler_integration",destination_path = "data/Destination/test_rclone_handler_integration", base_path = "", logger = None):
    logger.debug("--- Rclone Integration Check ---")
    rclone_flags = "--transfers, 8" # Comma delimited string of (key,value | key, )
    handler = RcloneHandler(destination_path, base_path, logger, rclone_flags)

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
        assert result_code == 0

        # Test 3: Copy a test file to destination
        logger.debug(f"\n3. Copying a test file to '{src_path}'...")
        file_path = f"{src_path}/Test1/Subfolder1/test1.txt"
        # handler is instantiated with destination_path. Method copy_file derives destination path from the src_path.
        # Path in scr_path after base_path is appended to destination path
        (result_code, result_output) = handler.copy_file(file_path)
        logger.debug(f"Copy_file output:\n{result_output}")
        assert result_code == 0

        # Test 4: Verify file existence on remote (using lsf)
        logger.debug("Verifying file on remote...")
        file_path = f"{src_path}/Test1/Subfolder1/test1.txt"
        dst_path = get_destination_path(file_path, base_path, destination_path)
        rclone_command = f"lsf, {dst_path}"
        (result_code, result_output) = handler.run_command(rclone_command)
        logger.debug(f"Remote content:\n{result_output}")
        file_name = os.path.basename(file_path)
        assert file_name in result_output

        # Test 5: Create a new file
        logger.debug("Create a new file on remote...")
        file_path = create_test_data(src_path, "Test1/Subfolder1/test3.txt")
        (result_code, result_output) = handler.copy_file(file_path)
        logger.debug(f"Copy result code: {result_code}")
        assert result_code == 0

        # Test 6: Emulate move file
        logger.debug("Move file ...")
        old_file_path = create_test_data(src_path, ["Test1/Subfolder1/test3.txt"])
        shutil.move(f"{src_path}/Test1/Subfolder1/test3.txt", f"{src_path}/Test1/Subfolder1/test3_moved.txt") 
        # Delete old file at destination
        (result_code, result_output) = handler.delete_file(old_file_path)
        assert result_code == 0  

        # Create new file at destination
        (result_code, result_output) = handler.copy_file(f"{src_path}/Test1/Subfolder1/test3_moved.txt")
        logger.debug(f"Copy result code: {result_code}")
        assert result_code == 0

        # Test 7: Copy entire folder
        logger.debug("Copy entire folder to destination ...")
        test_files = []
        test_files.append("Test1/Subfolder3/test1.txt")
        test_files.append("Test1/Subfolder3/test2.txt")
        file_path = create_test_data(src_path, test_files)
        head = os.path.dirname(file_path)
        (result_code, result_output) = handler.copy_folder(head)
        logger.debug(f"Copy result code: {result_code}")
        assert result_code == 0

        # Check if subolder has been copied to destination
        rclone_command = ["lsf", "--format", "tshp", "--separator", " | ", head] 
        (result_code, result_output) = handler.run_command(rclone_command)
        logger.debug(f"result_output:\n{result_output}")
        file_name = os.path.basename(file_path)
        assert file_name in result_output

        # Test 8: Remove entire folder and contents from destination
        logger.debug("Remove entire folder and contents from destination ...")
        test_files = []
        test_files.append("Test1/Subfolder3/test1.txt")
        test_files.append("Test1/Subfolder3/test2.txt")
        file_path = create_test_data(src_path, test_files)
        head = os.path.dirname(file_path)
        (result_code, result_output) = handler.delete_folder(head)
        assert result_code == 0

        # Check if subolder has been removed from destination
        dst_path = get_destination_path(head, base_path, destination_path)
        rclone_command = ["lsf", "--format", "tshp", "--separator", " | ", dst_path] 
        (result_code, result_output) = handler.run_command(rclone_command)
        assert result_code == 0
        file_name = os.path.basename(file_path)
        assert file_name not in result_output


        logger.debug("\n--- All integration checks passed! ---")

    except Exception as e:
        logger.debug(f"\n--- Integration check FAILED: {e} ---")
    finally:
        logger.debug(f"\n--- Integration check cleanup")
        # if os.path.exists(local_file_path):
        #     os.remove(local_file_path)


def create_test_data(path: str, files: list[str] | str):
    """
    Create files relative to path
    """

    if isinstance(files, str):
        file_list = [f"{files}"]
    else:
        file_list = files

    for filename in file_list:
        filename = filename.lstrip("/\\")
        file_path = os.path.join(path, filename)
        head = os.path.dirname(file_path)
        try:
            os.makedirs(head, exist_ok=True)
        except OSError as e:
            logger.debug(f"Error creating folder {head}: {e}")
            sys.exit(1)

        with open(file_path, 'w') as f:
            logger.debug(f"Writing to file {filename}")
            f.write(f"Test data for {filename}\n")

    return file_path

   
if __name__ == "__main__":
    if len(sys.argv) < 2:
        path = "data"
    else:
        path = sys.argv[1]

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
    root_logger.debug("Root logger configured with condole handler.")
    # --- End Central Logging Setup ---
 
    logger = logging.getLogger()
    logger.debug("Before calling run_integration_check")
    src_path = "data/Source/Cloud/test_rclone_handler_integration"
    # destination path of cloud storage is in format: <remote>:<bucket>/path
    # Example destination path of local storage: D:/my/local/path or /my/local/path
    destination_path = "e2:test-foldermonitor/Cloud/test_rclone_handler_integration"
    base_path = "Cloud"
    run_integration_check(src_path, destination_path, base_path, logger)

