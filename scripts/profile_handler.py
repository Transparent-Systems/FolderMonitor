import logging
import os
import configparser
from pathlib import Path

class ProfileHandler:
    def __init__(self, logger : logging.Logger = None,
                app_name : str = "foldermonitor",
                config_name : str = ""
                ):
        """
        Docstring for __init__
        
        :param self: Instance
        :param logger: Logger
        :type logger: logging.Logger
        :param app_name: The name of the application, like "foldermonitor" or "anotherapp"
        :type app_name: str
        """

        if (logger is None):
            logger = logging.getLogger(__name__)
            logger.setLevel(logging.DEBUG)
            # Create a formatter
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            # Create a console handler
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(formatter)
            # Add the console handler to the logger
            logger.addHandler(console_handler)
        else:
            logger = logger

        self.logger = logger
        self.app_name = app_name
        if not config_name:
            config_name = f"{app_name}.conf"
        self.config_name = config_name
        self.config_path = self._get_config_path(self.app_name, self.config_name)
        self.config_parser = configparser.ConfigParser()
        
        if self.config_path.exists():
            self.config_parser.read(self.config_path)
        else:
            logger.debug(f"Config path does not exist: {self.config_path}")

    def _get_config_path(self, app_name: str = None, config_name: str = None) -> Path:
        """Determines the platform-specific path for the config file."""

        if app_name is None:
            app_name = self.app_name
        if config_name is None:
            config_name = self.config_name

        if os.name == 'nt':  # Windows
            base_dir = Path(os.environ.get('APPDATA', Path.home() / 'AppData/Roaming'))
        else:  # Linux / Unix
            base_dir = Path.home() / '.config'
        
        return base_dir / app_name / f"{config_name}"

    def _save_config(self):
        """Saves the current configuration to the file."""
        if not self.config_path.parent.exists():
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            
        with open(self.config_path, 'w') as configfile:
            self.config_parser.write(configfile)

  
    def get_profile(self, profile_name: str) -> dict:
        """
        Get profile attributes from the config file.
        """

        if profile_name in self.config_parser:
            return self.config_parser[profile_name]
        else:
            return {}

    def get_profile_names(self) -> list:
        """
        Get a list of profile names.
        """
        return self.config_parser.sections()

    def add_profile(self, profile_name: str, profile: dict[str, str]) -> bool:
        """
        Adds a new profile.
        profile_name os the name of the profile (section name in ini file)
        profile is a dictionary with the profile attributes
        """
        if not profile_name:
            logger.debug("Profile name is missing. Is required to store profile in config file")                
            return False

        if self.config_parser.has_section(profile_name):
            self.logger.warning(f"Profile '{profile_name}' already exists. Use update_profile instead.")
            return False

        # Add profile_name to profile dictionary object
        # profile["profile_name"] = profile_name
        self.config_parser.add_section(profile_name)
        for key, value in profile.items():
            self.config_parser.set(profile_name, key, str(value))
        
        self._save_config()
        self.logger.debug(f"Profile '{profile_name}' added successfully.")
        return True

    def update_profile(self, profile_name: str, profile: dict[str, str]) -> bool:
        """
        Updates an existing profile.
        """
        # Get profile from remote profiles configuration
        current_profile = self.get_profile(profile_name)
        if not current_profile:
            self.logger.warning(f"Profile '{profile_name}' not found. Use add_profile instead.")
            return False

        # The result profile is the intersection of the current and the new profile
        # Update keys that are already present in current profile
        for key in profile:
            self.config_parser.set(profile_name, key, str(profile[key]))
        
        # Remove keys that are in current profile but not in the new profile
        for key in current_profile:
            if key not in profile:
                self.config_parser.remove_option(profile_name, key)
        
        self._save_config()
        self.logger.debug(f"Profile '{profile_name}' updated successfully.")
        return True

    def delete_profile(self, profile_name: str) -> bool:
        """
        Deletes a profile.
        """
        # Get profile from remote profiles configuration
        if not self.get_profile(profile_name):
            self.logger.warning(f"Profile '{profile_name}' not found.")
            # Profile name not in configuration, so nothing to do
            return True

        self.config_parser.remove_section(profile_name)
        self._save_config()
        self.logger.debug(f"Profile '{profile_name}' deleted successfully.")
        return True

# --- Example Usage ---
if __name__ == "__main__":
     # Set up logging
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    app_names = ["foldermonitor", "rclone"]
    profile_handlers = {}
    # Create profile handler for each app_name
    for app_name in app_names:
        profile_handler = ProfileHandler(
            logger=logger,
            app_name=app_name,
        )
        profile_handlers[app_name] = profile_handler

    profile_names = ["idrive-test", "r2", "drive", "profile_does_not_exist"]

    for profile_name in profile_names:
        print("=======================================")
        print(f"Profile_name: {profile_name}")
        print("=======================================")
        for app_name in app_names:
            profile_handler = profile_handlers[app_name]
            profile_attributes = profile_handler.get_profile(profile_name=profile_name)
            if profile_attributes:
                print(f"Profile: {profile_name} in {app_name} configuration")
                print(f"type: {profile_attributes.get('type')}")
            else:
                print(f"Profile '{profile_name}' not in {app_name} configuration")
