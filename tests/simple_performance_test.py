
import os
from pathlib import Path
import sys
import time
import logging

# Add the scripts directory to the Python path
scriptspath = Path(__file__).parent / Path("../scripts")
sys.path.insert(0, scriptspath.resolve().as_posix())

from base_handler import BaseHandler
from s3_handler import S3Handler
from rclone_handler import RcloneHandler

def main():
    logger = logging.getLogger()
    # logger.setLevel(logging.DEBUG)
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # Create console logger
    console_logger = logging.StreamHandler()
    console_logger.setFormatter(formatter)
    logger.addHandler(console_logger)

    # Create file logger
    file_logger = logging.FileHandler("logs/simple_performance_test.log")
    file_logger.setFormatter(formatter)
    logger.addHandler(file_logger)

    s3_handler = S3Handler(
        logger=logger,
        base_source_path="data/Source/idrive-cloud-storage/performance-test",
        base_remote_path="test-foldermonitor/idrive-cloud-storage/performance-test-s3",
        remote_profile="idrive-test",
        app_name="foldermonitor"
    )

    rclone_handler = RcloneHandler(
        logger=logger,
        base_source_path="data/Source/idrive-cloud-storage/performance-test",
        base_remote_path="test-foldermonitor/idrive-cloud-storage/performance-test-rclone",
        remote_profile="idrive-test"
    )

    NUMBER_OF_TESTS = 10
    logger.info(f"Simple performance test - number of tests: {NUMBER_OF_TESTS}")
    base_handlers = [s3_handler, rclone_handler]
    # base_handlers = [s3_handler]

    for base_handler in base_handlers:
        file = "data/Source/idrive-cloud-storage/performance-test/testfile-8kb.txt"
        test_copy_file_performance(
            logger=logger,
            base_handler=base_handler,
            source_path=file,
            number_of_tests=NUMBER_OF_TESTS
        )

        file = "data/Source/idrive-cloud-storage/performance-test/testfile-1mb.txt"
        # test_copy_file_performance(
        #     logger=logger,
        #     base_handler=base_handler,
        #     source_path=file,
        #     number_of_tests=3
        # )


def test_copy_file_performance(logger: logging.Logger, base_handler: BaseHandler, source_path: str, number_of_tests: int = 10):
    logger.info("=" * 20)
    base_class_name = base_handler.__class__.__name__
    logger.info(f"BEGIN: {base_class_name}")

    if not os.path.exists(source_path):
        logger.info(f"File {source_path} does not exist")
        sys.exit(1)

    now = time.time()
    error_count = 0
    # Create an artificial source path that we will use for deriving a new remote path for each iteration
    source_path_obj = Path(source_path)
    source_path_parent = source_path_obj.parent
    source_path_name = source_path_obj.name
    source_path_short = source_path_name.split('.')[0]
    ext_name = source_path_name.split('.')[1]

    for i in range(number_of_tests):
        source_path_virtual = f"{source_path_parent}/{source_path_short}-{i}.{ext_name}"
        # Derive remote_path from virtual source path
        remote_path = base_handler.get_remote_path(source_path=source_path_virtual)
        logger.info(f"Remote path: {remote_path}")
        (result_code, result_output) = base_handler.copy_file(source_path=source_path, remote_path=remote_path)
        if (result_code != 0):
            logger.info(f"Error: {result_output}")
            error_count += 1

    logger.info(f"Error count: {error_count}")
    duration = time.time() - now
    logger.info(f"Duration: {duration:.2f} seconds")
    logger.info(f"END: {base_class_name}")
    logger.info("=" * 20)

if __name__ == "__main__":
    main()

#
