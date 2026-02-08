from typing import List, Optional
from pydantic import BaseModel, ValidationError, ConfigDict
import yaml
import logging
import argparse

class ConfigModels:
    """Pydantic models for configuration validation."""
    class Testing(BaseModel):
        model_config = ConfigDict(extra='forbid')
        check_delay: int

    class Backup(BaseModel):
        model_config = ConfigDict(extra='forbid')
        interval: str

    class Monitor(BaseModel):
        # model_config = ConfigDict(extra='forbid')
        model_config = ConfigDict()
        name: str
        monitor_path: str
        remote_path: str
        remote_profiles: List[str]
        exclude_patterns: Optional[List[str]] = None
        testing: Optional['ConfigModels.Testing'] = None
        backup: Optional['ConfigModels.Backup'] = None

    class Config(BaseModel):
        model_config = ConfigDict(extra='forbid')
        version: str
        monitors: List['ConfigModels.Monitor']

    def validate(self, config_path: str = None, logger: logging.Logger = None) -> bool:
        # Configure console logger
        if logger is None:
            logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
            logger = logging.getLogger(__name__)

        try:
            logger.debug("Validating configuration...")
            logger.debug(f"config_path: {config_path}")
            config_file = config_path if config_path else "conf/config.test.yaml"
            with open(config_file, "r") as f:
                config_data = yaml.safe_load(f)
            
            config_model = self.Config(**config_data)
            
            logger.debug("Configuration is valid.")
            logger.debug(config_model.model_dump_json(indent=2))
            return True
        except ValidationError as e:
            logger.error("Configuration validation error:")
            for error in e.errors():
                logger.error(f"  - Location: {'.'.join(map(str, error['loc']))}")
                logger.error(f"    Message: {error['msg']}")
                logger.error(f"    Invalid value: {error.get('input')}")
                logger.error("    =============================")
        except FileNotFoundError:
            logger.error(f"Error: Configuration file '{config_file}' not found.")
        
        return False

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG, format='%(levelname)s: %(message)s')
    console_logger = logging.getLogger(__name__)
    parser = argparse.ArgumentParser(description="Load and validate a configuration file.")
    parser.add_argument("-c", "--config", 
                        default="conf/config.test.yaml", 
                        type=str, 
                        help="The path to the configuration file."
                        )
    args = parser.parse_args()
   
    config_models = ConfigModels()
    console_logger.debug("==========================================")
    if (config_models.validate(config_path=args.config, logger=console_logger)):
        console_logger.debug("Main - Configuration validation succeeded.")
    else:
        console_logger.error("Main - Configuration validation failed.")
    console_logger.debug("==========================================")
