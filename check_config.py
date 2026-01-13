import argparse
import logging
import sys
from pathlib import Path

# Add the scripts directory to the Python path
scriptspath = Path(__file__).parent / Path("scripts")
sys.path.insert(0, scriptspath.resolve().as_posix())

from config_models import ConfigModels


"""
    Check the configuration YAML file.
    By default this is conf/config.yaml.
    The path to the config file can eb changed with the --config-path argument.
    Call example:
        python check_config.py --config-path conf/config.yaml
"""
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
   
    config_models = ConfigModels()
    config_path = args.config_path
    if (config_models.validate(config_path=config_path, logger=console_logger)):
        console_logger.debug(f"Main - Configuration of {config_path} is valid.")
    else:
        console_logger.error(f"Main - Configuration of {config_path} failed.")
