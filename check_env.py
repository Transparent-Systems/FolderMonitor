import argparse
import logging
import sys
import os
import subprocess
import shutil

def check_setup(logger: logging.Logger, config_path: str) -> int:
    error_count = 0
    console_logger.debug("--- Folder Monitor: Environment Self-Test ---")
    
    # 1. Check Python Version
    console_logger.debug(f"[*] Python Version: {sys.version.split()[0]} - OK")

    # 2. Check for Config Folder/File
    if os.path.exists(config_path):
        console_logger.debug(f"[*] Config file found: {config_path} - OK")
    else:
        error_count += 1
        console_logger.debug(f"[!] ERROR: Config file NOT found at {config_path}")

    # 3. Check for rclone
    rclone_path = shutil.which("rclone")
    if rclone_path:
        console_logger.debug(f"[*] rclone found at: {rclone_path} - OK")
        try:
            version = subprocess.check_output(["rclone", "version"], text=True).split('\n')[0]
            console_logger.debug(f"    ({version})")
        except Exception:
            console_logger.debug("    [!] Warning: Could not execute rclone version.")
            error_count += 1
    else:
        console_logger.debug("[!] ERROR: 'rclone' not found in system PATH. Please install it from rclone.org.")
        error_count += 1

    # 4. Check for key Python dependencies
    try:
        import pydantic
        import watchdog
        import yaml
        console_logger.debug("[*] Python dependencies (pydantic, watchdog, yaml) - OK")
    except ImportError as e:
        console_logger.debug(f"[!] ERROR: Missing Python dependency: {e}")
        console_logger.debug("    Run 'pip install -r requirements.txt' to fix this.")
        error_count += 1

    return error_count

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG, format='%(levelname)s: %(message)s')
    console_logger = logging.getLogger(__name__)
    parser = argparse.ArgumentParser(description="Load and validate a configuration file.")
    parser.add_argument("--config-path", 
                        default="conf/config.yaml", 
                        type=str, 
                        help="The path to the configuration file."
                        )
    args = parser.parse_args()
    config_path = args.config_path

    error_count = check_setup(logger=console_logger, config_path=config_path)
    if error_count == 0:
        console_logger.debug("--- Folder Monitor: Environment Self-Test Completed successfully ---")
        console_logger.debug(f"--- Next step: check config.yaml file with command: python check_config.py --config-path {config_path}")
    else:
        console_logger.debug(f"--- Folder Monitor: Environment Self-Test - {error_count} tests failed ---")


