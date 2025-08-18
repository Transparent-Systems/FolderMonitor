import os
import shutil
import time
import sys
from pathlib import Path

"""
This script contains utility static methods and classes
"""


def create_test_data(path: str, files: list[str]) -> Path:
    """
    Create files relative to path.
    Returns the path to the last created file.
    """

    for file_name in files:
        file_name = file_name.lstrip("/\\")
        try:
            file_path = Path(path) / Path(file_name)
            parent_path = file_path.parent
            if not parent_path.exists():
                parent_path.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            sys.exit(1)

        try:
            file_path.write_text(f"Test data for {file_path.as_posix}\n")
        except Exception as e:
            sys.exit(1)

    return file_path


def delete_test_data(path: str, files: list[str]) -> Path:
    """
    Delete files in path
    """

    for file_name in files:
        try:
            file_name = file_name.lstrip("/\\")
            file_path = Path(path) / Path(file_name)
            if file_path.exists():
                if file_path.is_file():
                    file_path.unlink()
                else:
                    shutil.rmtree(path=file_path)
        except Exception as e:
            continue

    return file_path


class ProcessTestResult:
    """
    Class to store and retrieve test results
    """

    def __init__(self, testsuite_name: str):
        self.testsuite_name = testsuite_name
        self.success_count = 0
        self.failure_count = 0
        self.test_results: list[dict] = []
        self.start_time = time.perf_counter()
        self.test_time = self.start_time
        self.duration = 0
        self.test_counter = 0

    def process(
        self,
        test_case_name: str,
        test_ok: bool,
        test_output: str | list,
        test_step_name="",
    ):
        """
        Process test result.
        Calculates success and failure count and stores these metrics, result outputand identifiers in test_result
        The test results can be retrieved later on in method get_test_results
        """
        # --- Calculations
        end_time = time.perf_counter()
        test_duration = end_time - self.test_time
        self.test_time = end_time
        self.duration = end_time - self.start_time
        self.test_counter += 1

        if test_ok:
            self.success_count += 1
        else:
            self.failure_count += 1

        result_output_list = [str]

        if isinstance(test_output, str):
            result_output_list.append(test_output)
        else:
            result_output_list = test_output

        test_result = {
            "test_case_name": test_case_name,
            "test_step_name": test_step_name,
            "test_counter": self.test_counter,
            "test_ok": test_ok,
            "test_duration": test_duration,
            "test_output": result_output_list,
        }
        self.test_results.append(test_result)

    def get_test_results(self) -> list[dict]:
        return self.test_results
