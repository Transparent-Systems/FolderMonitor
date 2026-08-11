from multiprocessing.util import close_all_fds_except
import sys
from pathlib import Path
import argparse
import logging
import unittest

from botocore.credentials import ProcessProvider
from watchdog.watchmedo import command

# Add the scripts directory to the Python path
scripts_path = Path(__file__).parent / Path("../scripts")
if not scripts_path in sys.path:
    sys.path.insert(0, scripts_path.resolve().as_posix())

from utils.logging_util import get_unique_logger
from command_processor import CommandProcessor
from database_test_data import DatabaseTestData

class TestCommandProcessor(unittest.TestCase):
    """
    Test CommandProcessor
    The main purpose of TestCommandProcessor is to test the CommandProcessor class.
    This avoids havng to manually run folder monitor with the corresponding command.
    Additionaly, this class uses the test SQLite datbase in folder tests/data
    You can run individual tests using paramater test_cases which is a space delimited string of test methods.
    Only part of the test method name is used for matching.
    For example: python3 tests/test_command_processor.py -tests_cases "_01 _02"
    """

    logger: logging.Logger
    command_processor: CommandProcessor
    db_path = "tests/data/foldermonitor.sqlite"
    dotenv_path = "tests/data/.env"
    
    @classmethod
    def setUpClass(cls):
        cls.logger.info(f"Start testing CommandProcessor")
        cls.command_processor = CommandProcessor(
            logger=cls.logger,
            db_path=cls.db_path
        )
        cls.database_test_data = DatabaseTestData(
            logger=cls.logger,
            db_path=cls.db_path,
            dotenv_path=cls.dotenv_path
        )
        cls.database_test_data.remove_test_data()
        cls.database_test_data.load_test_data()

    @classmethod
    def tearDownClass(cls):
        # Perform any necessary cleanup after all tests have run
        cls.logger.info(f"TearDown finished")

    def test_01_profile_new(self):
        self.command_processor.profile_new()

    def test_02_profile_edit(self):
        self.command_processor.profile_edit()
        
    def test_03_profile_test(self):
        self.command_processor.profile_test()

    def test_04_profile_test(self):
        # Get first profile and use profile id in call to profile_test()
        profiles = self.command_processor.sqlite_handler.get_profiles()
        if not profiles:
            self.skipTest("No profiles found in database")
        first_profile_id = profiles[0]["id"]
        self.command_processor.profile_test(profile_id=first_profile_id)

    def test_05_profile_delete(self):
        self.command_processor.profile_delete()

    def test_10_monitor_new(self):
        self.command_processor.monitor_new()

    def test_11_monitor_edit(self):
        self.command_processor.monitor_edit()

    def test_12_monitor_show(self):
        self.command_processor.monitor_show()

    def test_13_monitor_delete(self):
        self.command_processor.monitor_delete()

    def test_14_monitor_test(self):
        self.command_processor.monitor_test()
    
    # def test_15_monitor_start(self):
    #     self.command_processor.monitor_start()

    # def test_16_monitor_stop(self):
    #     self.command_processor.monitor_stop()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run integration tests for command_processor using unittest."
    )
    parser.add_argument(
        "-d",
        "--db-path",
        type=str,
        default="tests/data/foldermonitor.sqlite",
        help="Path to database file."
    )
    parser.add_argument(
        "-e",
        "--dotenv-path",
        type=str,
        default="tests/data/.env",
        help="Path to .env file."
    )
    parser.add_argument(
        "--test-cases",
        type=str,
        nargs="+",
        help="Space-separated list of test method names (or substrings) to run."
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
    logger.info("Starting command processor tests")

    # Initialize TestCommandProcessor class variables
    TestCommandProcessor.logger = logger
    TestCommandProcessor.db_path = args.db_path
    TestCommandProcessor.dotenv_path = "tests/data/.env"

    # Populate database with test data
    database_test_data = DatabaseTestData(
        logger=logger,
        db_path=args.db_path,
        dotenv_path=args.dotenv_path
    )

    # Run Tests
    test_loader = unittest.TestLoader()
    full_suite = test_loader.loadTestsFromTestCase(TestCommandProcessor)

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
