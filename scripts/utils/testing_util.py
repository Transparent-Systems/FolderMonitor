import os
import shutil
import time
import sys

"""
This script contains utility static methods and classes
"""


def create_test_data(path: str, files: list[str] | str):
    """
    Create files relative to path
    If files is empty then create folder
    """

    if isinstance(files, str):
        file_list = [f"{files}"]
    else:
        file_list = files

    # If file_list is empty then this is a folder
    if len(file_list) == 0:
        try:
            os.makedirs(path, exist_ok=True)
        except OSError as e:
            sys.exit(1)
        return path

    for filename in file_list:
        filename = filename.lstrip("/\\")
        file_path = os.path.join(path, filename)
        head = os.path.dirname(file_path)
        try:
            os.makedirs(name=head, exist_ok=True)
        except OSError as e:
            sys.exit(1)

        try:
            with open(file_path, 'w') as f:
                f.write(f"Test data for {file_path}\n")
        except Exception as e:
            sys.exit(1)

    return file_path


def delete_test_data(path: str, files: list[str] | str):
    """
    Delete files relative to path
    """

    if isinstance(files, str):
        file_list = [f"{files}"]
    else:
        file_list = files

    for filename in file_list:
        try:
            filename = filename.lstrip("/\\")
            filepath = os.path.join(path, filename)
            if (os.path.isfile(filepath)):
                os.remove(filepath)
            else:
                shutil.rmtree(path=filepath)
        except Exception as e:
            continue
    
    return filepath


class ProcessTestResult():
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

    def process(self, test_case_name: str, test_ok: bool, test_output: str | list, test_step_name = ""):
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
            "test_case_name" : test_case_name,
            "test_step_name" : test_step_name,
            "test_counter" : self.test_counter,
            "test_ok" : test_ok,
            "test_duration" : test_duration,
            "test_output" : result_output_list
        }
        self.test_results.append(test_result)

    def get_test_results(self) -> list[dict]:
        return (self.test_results)


