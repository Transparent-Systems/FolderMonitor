import sys
import os
# Append app root folder if needed
root_folder = os.path.join(os.path.dirname(__file__), '..')
root_folder_abs = os.path.abspath(root_folder)
if root_folder_abs not in sys.path:
    sys.path.append(root_folder_abs)

from scripts.utils.diagnostic_util import DiagnosticUtil

diagnostic_util = DiagnosticUtil(
    logger=None
)

if __name__ == "__main__":

    # Check args for test_case
    if len(sys.argv) > 1:
        test_cases = sys.argv[1:]
    else:
        test_cases = []

    if len(test_cases) == 0:
        test_cases = ["check_app_config"]

    if ("check_app_env" in test_cases):
        if (diagnostic_util.check_app_env(config_path="tests/conf/config.test.yaml")):
            print("Env check passed")
        else:
            print("Env check failed")

    elif ("check_profile_import" in test_cases):
        if diagnostic_util.check_profile_import():
            print("Profile import passed")
        else:
            print("Profile import failed")

    elif ("check_rclone_dependency" in test_cases):
        if diagnostic_util.check_rclone_dependency(config_path="tests/conf/config.test.yaml"):
            print("Check for Rclone dependency passed")
        else:
            print("Check for Rclone dependency failed")

    elif ("check_app_config" in test_cases):
        if (diagnostic_util.check_monitor_config(config_path="tests/conf/config.test.yaml")):
            print("Config check passed")
        else:
            print("Config check failed")
    else:
        print("No test cases selected")


    # diagnostic_util.print_overview()
    

    sys.exit(0)
