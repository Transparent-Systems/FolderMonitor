import logging
import os
from pathlib import Path
import sys
from botocore.exceptions import ClientError
from version import __version__

root_folder = os.path.join(os.path.dirname(__file__), '../..')
root_folder_abs = os.path.abspath(root_folder)
if root_folder_abs not in sys.path:
    sys.path.append(root_folder_abs)

from scripts.profile_handler import ProfileHandler
from scripts.s3_factory import S3Factory
from scripts.utils.diagnostic_util import DiagnosticUtil

class CommandProcessor:
    """
    Processes commands for the FolderMonitor application.
    """

    def __init__(self, logger: logging.Logger):
        self.logger = logger
        # Filter logging to avoid noise on the console
        self.logger.setLevel(logging.WARNING)
        self.logger.propagate = False

        # Silence boto3 and other libraries
        logging.getLogger("boto3").setLevel(logging.WARNING)
        logging.getLogger("botocore").setLevel(logging.WARNING)
        logging.getLogger("s3transfer").setLevel(logging.WARNING)
        logging.getLogger("urllib3").setLevel(logging.WARNING)

        self.diagnostic_util = DiagnosticUtil(logger=self.logger)


    def process_command(self, command: str, subcommand: str=None, arguments: dict = None):
        """
        Routes commands and subcommands to their respective functions.
        """
        try:
            self.logger.debug(f"Processing command: {command} with subcommand: {subcommand}")
            if arguments is not None:
                if "config_path" in arguments:
                    config_path = arguments["config_path"]
                if "profile_name" in arguments:
                    profile_name = arguments["profile_name"]
            else:
                config_path = None
                profile_name = None
            
            # Process command
            # Unknown commands and subcommands have already been intercepted by argparse
            if command == "test":
                self.command_test(config_path=config_path)
            elif command == "version":
                # Convert tuple format to 2.0.0
                version = f"{__version__[0]}.{__version__[1]}.{__version__[2]}"
                print(f"FolderMonitor v{version}")
            elif command == "profile":
                if subcommand == "show":
                    self.command_profile_show()
                elif subcommand == "file":
                    self.command_profile_file()
                elif subcommand == "import":
                    self.command_profile_import()
                elif subcommand == "new":
                    self.command_profile_new()
                elif subcommand == "edit":
                    self.command_profile_edit()
                elif subcommand == "delete":
                    self.command_profile_delete()
                elif subcommand == "test":
                    self.command_profile_test(profile_name=profile_name)
                else:
                    self.logger.warning(f"Unknown profile subcommand: {subcommand}")
            elif command == "config":
                if subcommand == "file":
                    self.command_config_file(config_path=config_path)
                elif subcommand == "show":
                    self.command_config_show(config_path=config_path)
                else:
                    self.logger.warning(f"Unknown config subcommand: {subcommand}")
            else:
                self.logger.warning(f"Unknown command: {command}")
        except KeyboardInterrupt:
            print("\nOperation cancelled by user.")
            return

    def command_test(self,config_path):
        try:
            diagnostic_util = DiagnosticUtil(logger=self.logger)
            if (not diagnostic_util.check_app_env(
                config_path=config_path
                )):
                return

            diagnostic_util.check_profile_import()

            if not diagnostic_util.check_rclone_dependency(
                config_path=config_path
                ):
                return

            if not diagnostic_util.check_app_config(
                config_path=config_path
                ):
                return
            
            diagnostic_util.print_overview()
            return
        finally:
            print("Exiting test mode now")


    def command_config_show(self, config_path: str):
        """
        Show contents of config file
        """

        if config_path is None:
            config_path = "conf/config.yaml"

        # Check if config_path exists
        config_path = Path(config_path).resolve()
        if not config_path.exists():
            print(f"Config file '{config_path}' does not exist.")
            return
        
        # Show contents of file at config_path
        print(f"Contents of config file at {config_path}:")
        with open(config_path, "r") as file:
            print(file.read())

        print("==== End of content ===")
        print(f"==== Config location: {config_path} ===")


    def command_config_file(self, config_path: str):
        """
        Print location of config file
        """

        # Check if config_path exists
        config_path = Path(config_path).resolve()
        if not config_path.exists():
            print(f"Config file '{config_path}' does not exist.")
            return
        
        print(f"Config location: {config_path}")

        # Optionally show other yaml files in the parent folder
        parent_folder = Path(config_path).parent
        if parent_folder.exists():
            yaml_files = list(parent_folder.glob("*.yaml"))
            if len(yaml_files) > 0:
                print(f"Other yaml files in parent folder: {parent_folder}")
                for yaml_file in yaml_files:
                    if yaml_file == config_path:
                        continue
                    print(f"   {yaml_file}")
            else:
                print(f"No other yaml files in parent folder: {parent_folder}")  
   

    def command_profile_test(self, profile_name: str = None):
        """
        Test selected profile
        """

        profile_handler = ProfileHandler(
            logger=self.logger,
            app_name="foldermonitor",
            config_name="foldermonitor.conf"
        )

        if profile_name is None:
            # Show all profiles
            profile_names = profile_handler.get_profile_names()

            if profile_name:
                if profile_name not in profile_names:
                    print(f"Profile '{profile_name}' not found.")
                    return
            else:
                for i in range(len(profile_names)):
                    print(f"{i+1}. {profile_names[i]}")

                # Currently the only native profile type is S3
                # Prompt user for profile_name
                while True:
                    # Show all profiles
                    profile_names = profile_handler.get_profile_names()
                    for i in range(len(profile_names)):
                        print(f"{i+1}. {profile_names[i]}")

                    profile_number = input("Enter profile number: ")
                    print(f"You entered profile number: {profile_number}")
                    if profile_number.isdigit():
                        profile_number = int(profile_number)
                        if profile_number > 0 and profile_number <= len(profile_names):
                            profile_name = profile_names[profile_number-1]
                            break
                    print(f"Invalid profile number: {profile_number}. Please try again.")

            print(f"You selected profile: {profile_name}")
        else:
            print(f"You selected profile: {profile_name}")

        # Get s3_client from S3ConnectionFactory
        s3_factory = S3Factory(
            logger=self.logger,
            app_name="foldermonitor"
        )

        s3_client = s3_factory.get_client_from_remote(profile_name=profile_name)
        # Get bucket list using s3_client
        try:
            buckets = s3_client.list_buckets()
            if buckets is None or 'Buckets' not in buckets:
                print(f"No buckets found on remote profile name: {profile_name}")
            else:
                print("Buckets:")
                for bucket in buckets["Buckets"]:
                    print(f"Bucket: {bucket['Name']}")

        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code')
            if error_code == 'AccessDenied':
                print("Connection successful! (ListBuckets permission denied).")
                print("Your credentials are valid, but restricted.")
            else:
                print(f"Error: {e}")
                print(f"Test for profile '{profile_name}' failed")
                return
        except Exception as e:
            print(f"Error: {e}")
            print(f"Test for profile '{profile_name}' failed")
            return

        print(f"Profile test for '{profile_name}' successful")
      
    def command_profile_delete(self):
        """
        """

        profile_handler = ProfileHandler(
            logger=self.logger,
            app_name="foldermonitor",
            config_name="foldermonitor.conf"
        )

        # Show all profiles
        profile_names = profile_handler.get_profile_names()
        for i in range(len(profile_names)):
            print(f"{i+1}. {profile_names[i]}")

        # Prompt user for profile_name
        while True:
            while True:
                profile_number = input("Enter profile number to delete: ")
                print(f"You entered profile number: {profile_number}")
                if profile_number.isdigit():
                    profile_number = int(profile_number)
                    if profile_number > 0 and profile_number <= len(profile_names):
                        break
                print(f"Invalid profile number: {profile_number}. Please try again.")

            while True:
                profile_number_repeat = input("Repeat profile number to delete: ")
                print(f"You entered profile number: {profile_number_repeat}")
                if profile_number_repeat.isdigit():
                    profile_number_repeat = int(profile_number_repeat)
                    if profile_number_repeat > 0 and profile_number_repeat <= len(profile_names):
                        break
                print(f"Invalid profile number: {profile_number_repeat}. Please try again.")

            if profile_number == profile_number_repeat:
                break
            print(f"Profile numbers do not match: {profile_number} is not {profile_number_repeat}. Please try again.")

        profile_name = profile_names[profile_number-1]
        print(f"You want to delete profile: {profile_name}")

        if (profile_handler.delete_profile(
            profile_name=profile_name)
            ):
            print(f"Profile name: {profile_name} deleted")
        else:
            print(f"Profile name: {profile_name} not deleted")

    def command_profile_edit(self):
        """
        """

        profile_handler = ProfileHandler(
            logger=self.logger,
            app_name="foldermonitor",
            config_name="foldermonitor.conf"
        )

        # Currently the only native profile type is S3
        profile_type = "s3"
        # Prompt user for profile_name
        while True:
            # Show all profiles
            profile_names = profile_handler.get_profile_names()
            for i in range(len(profile_names)):
                print(f"{i+1}. {profile_names[i]}")

            profile_number = input("Enter profile number: ")
            print(f"You entered profile number: {profile_number}")
            if profile_number.isdigit():
                profile_number = int(profile_number)
                if profile_number > 0 and profile_number <= len(profile_names):
                    break
            print(f"Invalid profile number: {profile_number}. Please try again.")

        profile_name = profile_names[profile_number-1]
        print(f"You selected profile: {profile_name}")

        # Show providers
        while True:
            print("Enter provider number")
            print("1. Amazon AWS")
            print("2. Cloudflare R2")
            print("3. IDrive E2")
            print("4. Backblaze B2")
            print("5. Other")
            # Show current provider name
            profile = profile_handler.get_profile(profile_name)
            profile_provider = profile["provider"]
            print(f"Current provider: {profile_provider}")
            print("Press Enter to continue with current provider")
            provider_number = input("Enter provider number: ")
            if provider_number.strip()  == "":
                # Restore profile provider
                profile_provider = profile["provider"]
                break
            if provider_number == "1":
                profile_provider = "Amazon AWS"
            elif provider_number == "2":
                profile_provider = "Cloudflare R2"
            elif provider_number == "3":
                profile_provider = "IDrive E2"
            elif provider_number == "4":
                profile_provider = "Backblaze B2"
            elif provider_number == "5":
                profile_provider = "Other"
            else:
                print(f"Invalid provider number: {provider_number}. Please try again.")
                continue
            break

        # Show current access key
        profile_access_key = profile["access_key_id"]
        print(f"Current access key: {profile_access_key}")
        print("Press Enter to continue with current S3 access key")

        # Prompt user for access key
        while True:
            profile_access_key = input(f"Enter S3 access key id of your provider: {profile_provider}: ")
            if profile_access_key.strip() == "":
                # Restore access key
                profile_access_key = profile["access_key_id"]
            break

        # Show current secret key
        profile_secret_key = profile["secret_access_key"]
        print(f"Current secret key: {profile_secret_key}")
        print("Press Enter to continue with S3 secret key")

        # Prompt user for secret key
        while True:
            print("Please enter access secret key: ")
            profile_secret_key = input("Please enter secret key: ")
            if profile_secret_key.strip() == "":
                profile_secret_key = profile["secret_access_key"]
            break

        # Prompt user for region
        profile_region = None
        profile_endpoint = None
        # For Amazon we need the region
        # For other providers we need the endpoint
        if provider_number == "1": # Amazon AWS
            while True:
                # Show current region
                if "region" in profile:
                    print(f"Current region: {profile_region}")
                    print("Press Enter to continue with current region")
                    # Prompt user for region
                    profile_region = input(f"Enter S3 region of your provider: {profile_provider}: ")
                    if profile_region.strip()  == "":
                        # Restore region
                        profile_region = profile["region"]
                    break
                else:
                    # Prompt user for region
                    profile_region = input(f"Enter S3 region of your provider: {profile_provider}: ")
                    if profile_region.strip()  == "":
                        print("Region cannot be just spaces. Please try again.")
                        continue
                    break
        else:
            while True:
                if "endpoint" in profile:
                    profile_endpoint = input(f"Enter S3 endpoint from your provider: {profile_provider}: ")
                    if profile_endpoint.strip() == "":
                        # Restore profile_endpoint
                        profile_endpoint = profile["endpoint"]
                        break
                else:
                    profile_endpoint = input(f"Enter S3 endpoint from your provider: {profile_provider}: ")
                    if profile_endpoint.strip() == "":
                        print("Endpoint cannot be just spaces. Please try again.")
                        continue
                    break

        # Create profile
        profile_attributes = {
            "type": profile_type,
            "provider": profile_provider,
            "access_key_id": profile_access_key,
            "secret_access_key": profile_secret_key,
        }

        if provider_number == "1": # Amazon
            profile_attributes["env_auth"] = "false"
            profile_attributes["region"] = profile_region
        else:
            profile_attributes["endpoint"] = profile_endpoint

        if (profile_handler.update_profile(
            profile_name=profile_name,
            profile=profile_attributes)
            ):
            print(f"Profile name: {profile_name} updated")
        else:
            print(f"Profile name: {profile_name} not updated")

        print("Please test profile with one of the following commands:")
        print(f"   Windows command: folder_monitor.exe profile test --profile {profile_name}")
        print(f"   Linux or Windows command: python folder_monitor.py profile test --profile {profile_name}")


    def command_profile_new(self):
        """
        """

        profile_handler = ProfileHandler(
            logger=self.logger,
            app_name="foldermonitor",
            config_name="foldermonitor.conf"
        )

        # Currently the only native profile type is S3
        profile_type = "s3"

        # Prompt user for profile_name
        while True:
            profile_name = input("Enter profile name: ")
            print(f"You entered profile name: {profile_name}")

            # Check if profile_name already exists
            profile = profile_handler.get_profile(profile_name)
            if profile is None or profile == {}:
                break
            print(f"Profile name: {profile_name} already exists. Please try again")

        while True:
            print("Enter provider number")
            print("1. Amazon AWS")
            print("2. Cloudflare R2")
            print("3. IDrive E2")
            print("4. Backblaze B2")
            print("5. Other")
            provider_number = input("Enter provider number: ")
            if provider_number == "1":
                profile_provider = "Amazon AWS"
            elif provider_number == "2":
                profile_provider = "Cloudflare R2"
            elif provider_number == "3":
                profile_provider = "IDrive E2"
            elif provider_number == "4":
                profile_provider = "Backblaze B2"
            elif provider_number == "5":
                profile_provider = "Other"
            else:
                print(f"Invalid provider number: {provider_number}. Please try again.")
                continue
            break

        while True:
            profile_access_key = input(f"Enter S3 access key id of your provider: {profile_provider}: ")
            print(f"You entered access key: {profile_access_key}")
            if profile_access_key.strip() == "":
                print("Access key id cannot be empty. Please try again.")
                continue
            break
        
        while True:
            profile_secret_key = input(f"Enter S3 access secret key of your provider: {profile_provider}: ")
            print(f"You entered access key: {profile_secret_key}")
            if profile_access_key.strip() == "":
                print("Access secret key cannot be empty. Please try again.")
                continue
            break

        profile_region = None
        profile_endpoint = None
        if provider_number == "1": # Amazon
            while True:
                profile_region = input(f"Enter S3 region of your provider: {profile_provider}: ")
                print(f"You entered region: {profile_region}")
                if profile_region.strip() == "":
                    print("Region cannot be empty. Please try again.")
                    continue
                break
        else:
            while True:
                profile_endpoint = input(f"Enter S3 endpoint from your provider: {profile_provider}: ")
                print(f"You entered endpoint: {profile_endpoint}")
                if profile_endpoint.strip() == "":
                    print("Endpoint cannot be empty. Please try again.")
                    continue
                break

        # Create profile
        # Create profile
        profile_attributes = {
            "type": profile_type,
            "provider": profile_provider,
            "access_key_id": profile_access_key,
            "secret_access_key": profile_secret_key,
        }

        if provider_number == "1": # Amazon
            profile_attributes["env_auth"] = "false"
            profile_attributes["region"] = profile_region
        else:
            profile_attributes["endpoint"] = profile_endpoint

        if (profile_handler.add_profile(
            profile_name=profile_name,
            profile=profile_attributes)
            ):
            print(f"Profile name: {profile_name} created")
        else:
            print(f"Profile name: {profile_name} not created")

        print("Please test profile with one of the following commands:")
        print(f"   Windows command: folder_monitor.exe profile test --profile {profile_name}")
        print(f"   Linux or Windows command: python folder_monitor.py profile test --profile {profile_name}")


    def command_profile_show(self):
        """
        """
        # Show all profiles
        profile_handler = ProfileHandler(
            logger=self.logger,
            app_name="foldermonitor",
            config_name="foldermonitor.conf"
        )

        profile_names = profile_handler.get_profile_names()
        if (profile_names is None or len(profile_names) == 0):
            print(f"No profiles found in {profile_handler.config_path}")
            return

        for profile_name in profile_names:
            print(f"Profile name: {profile_name}")
            profile = profile_handler.get_profile(profile_name)
            for key in profile:
                print(f"   {key}: {profile[key]}")

    def command_profile_file(self):
        profile_handler = ProfileHandler(
            logger=self.logger,
            app_name="foldermonitor",
            config_name="foldermonitor.conf"
        )

        file_location = profile_handler.config_path
        print(f"Profile location: {file_location}")


    def command_profile_import(self):
        """
        Import profiles from rclone
        """
        self.diagnostic_util.check_profile_import()
