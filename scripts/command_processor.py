import json
import logging
from logging import config
import os
from pathlib import Path
import sys
from typing import Any
from unittest import result
from botocore.exceptions import ClientError
from version import __version__

root_folder = os.path.join(os.path.dirname(__file__), '../')
root_folder_abs = os.path.abspath(root_folder)
if root_folder_abs not in sys.path:
    sys.path.append(root_folder_abs)

from scripts.s3_factory import S3Factory
from scripts.rclone_handler import RcloneHandler
from scripts.utils.diagnostic_util import DiagnosticUtil
from scripts.sqlite_handler import SQLiteHandler

class CommandProcessor:
    """
    Processes command line commands for the FolderMonitor application.
    """

    def __init__(self, logger: logging.Logger, db_path: str):
        self.logger = logger
        # Filter logging to avoid noise on the console
        self.logger.setLevel(logging.WARNING)
        self.logger.propagate = False
        self.db_path = db_path

        # Silence boto3 and other libraries
        logging.getLogger("boto3").setLevel(logging.WARNING)
        logging.getLogger("botocore").setLevel(logging.WARNING)
        logging.getLogger("s3transfer").setLevel(logging.WARNING)
        logging.getLogger("urllib3").setLevel(logging.WARNING)

        self.diagnostic_util = DiagnosticUtil(
            db_path=db_path,
            logger=self.logger
            )
        self.sqlite_handler = SQLiteHandler(
            logger=self.logger,
            db_path=db_path
        )

    def version(self):
        """
        Show application version
        """
        version = f"({__version__[0]}.{__version__[1]}.{__version__[2]})"
        print(f"FolderMonitor version: {version}")


    def monitor_show(self):
        """
        Show all monitors
        """

        monitors = self.sqlite_handler.get_monitors()
        for monitor in monitors:
            print("")
            print("=" * 50)
            print(f"Monitor name: {monitor.get('name', 'N/A')}")
            print(f"Monitor type: {monitor.get('monitor_type', 'N/A')}")
            print(f"Monitor path: {monitor.get('monitor_path', 'N/A')}")
            print(f"Remote path: {monitor.get('remote_path', 'N/A')}")
            print(f"Status: {monitor.get('status', 'N/A')}")
            config = monitor.get("config", {})
            for key in config.keys():
                print(f"   {key}: {config.get(key, 'N/A')}")
            print("=" * 50)

    def _is_period_valid(self, period: str):
        """
        Check if period is valid
        """

        # Check if input_period is valid
        # Valid examples: 10, 10m, 10h, 10d
        if period.isdigit():
            return True

        if len(period) > 1:
            if period[-1].lower() in ['m', 'h', 'd'] and period[:-1].isdigit():
                return True
            else:
                return False
        else:
            return True

    def monitor_delete(self):
        """
        Delete monitor
        """

        monitors = self.sqlite_handler.get_monitors()
        if not monitors:
            print(f"No monitors found in {self.sqlite_handler.db_path}")
            return
        
        while True:
            # Show all monitors
            for i in range(len(monitors)):
                print(f"{i+1}. {monitors[i].get('name', 'N/A')}")

            input_monitor_number = input("Enter monitor number: ")
            if input_monitor_number == "":
                print("No monitor selected")
                return

            # Check if input_monitor_number is numeric
            if not input_monitor_number.isdigit():
                print(f"Invalid monitor number: {input_monitor_number}. Please try again.")
                continue

            input_monitor_number = int(input_monitor_number)    
            # Check if input_monitor_number is in valid range
            if input_monitor_number > 0 and input_monitor_number <= len(monitors):
                break
            else:
                print(f"Invalid monitor number: {input_monitor_number}. Please try again.")
        
        monitor = monitors[int(input_monitor_number) -1]
        print(f"You want to delete monitor: {monitor.get('name', 'N/A')}")

        # Ask to confirm monitor number
        while True:
            # Show all monitors
            for i in range(len(monitors)):
                print(f"{i+1}. {monitors[i].get('name', 'N/A')}")

            input_monitor_type_number_confirm = input("Confirm monitor number: ")
            if input_monitor_type_number_confirm == "":
                print("No monitor selected")
                return

            # Check if input_monitor_type_number_confirm is numeric
            if not input_monitor_type_number_confirm.isdigit():
                print(f"Invalid monitor number: {input_monitor_type_number_confirm}. Please try again.")
                continue

            input_monitor_type_number_confirm = int(input_monitor_type_number_confirm)    
            # Check if input_monitor_type_number_confirm is in valid range
            if input_monitor_type_number_confirm > 0 and input_monitor_type_number_confirm <= len(monitors):
                if input_monitor_type_number_confirm == input_monitor_number:
                    break
                else:
                    print(f"Monitor numbers do not match: {input_monitor_number} is not {input_monitor_type_number_confirm}. Please try again.")
                    continue
            else:
                print(f"Invalid monitor number: {input_monitor_type_number_confirm}. Please try again.")
                continue
        
        monitor = monitors[int(input_monitor_number) -1]
        print(f"You want to delete monitor: {monitor.get('name', 'N/A')}")

        if self.sqlite_handler.delete_monitor(
            monitor_id=monitor.get("id", 0)):
            print(f"Monitor name: {monitor.get('name', 'N/A')} deleted")
        else:
            print(f"Monitor name: {monitor.get('name', 'N/A')} not deleted")


    def monitor_edit(self):
        """
        Edit monitor
        """

        monitors = self.sqlite_handler.get_monitors()
        if not monitors:
            print(f"No monitors found in {self.sqlite_handler.db_path}")
            return
        
        print("\nList of monitors to edit")
        while True:
            # Show all monitors
            for i in range(len(monitors)):
                print(f"{i+1}. {monitors[i].get('name', 'N/A')}")

            input_monitor_number = input("Enter monitor number: ")
            if input_monitor_number == "":
                print("No monitor selected")
                return

            # Check if input_monitor_number is numeric
            if not input_monitor_number.isdigit():
                print(f"Invalid monitor number: {input_monitor_number}. Please try again.")
                continue

            input_monitor_number = int(input_monitor_number)    
            # Check if input_monitor_number is in valid range
            if input_monitor_number > 0 and input_monitor_number <= len(monitors):
                break
            else:
                print(f"Invalid monitor number: {input_monitor_number}. Please try again.")
        
        monitor = monitors[input_monitor_number-1]
        monitor_id = monitor.get("id", "N/A")

        # Get new monitor_name. Enter means keep current value
        while True:
            # Show current monitor name
            print(f"Current monitor name: {monitor.get('name', 'N/A')}")
            print("Press Enter to keep current monitor name")
            input_monitor_name = input("Enter new monitor name: ")
            if input_monitor_name.strip() == "":
                break
            monitor["name"] = input_monitor_name
            break

        # Get new monitor_path. Enter means keep current value
        while True:
            # Show current monitor path
            print(f"Current monitor path: {monitor.get('monitor_path', 'N/A')}")
            print("Press Enter to keep current monitor path")
            input_monitor_path = input("Enter new monitor path: ")
            if input_monitor_path.strip() == "":
                break
            monitor["monitor_path"] = input_monitor_path
            break

        # Get new remote_path. Enter means keep current value
        while True:
            # Show current remote path
            print(f"Current remote path: {monitor.get('remote_path', 'N/A')}")
            print("Press Enter to keep current remote path")
            input_remote_path = input("Enter new remote path: ")
            if input_remote_path.strip() == "":
                break
            monitor["remote_path"] = input_remote_path
            break

        # Get new monitor_type. Enter means keep current value
        # Show all monitor types
        monitor_types = self.sqlite_handler.get_lookup_table(
            table_name="monitor_types"
        )
        if monitor_types is None or len(monitor_types) == 0:
            print(f"No monitor types found in {self.sqlite_handler.db_path}")
            return
        
        print("List of monitor types")
        print("=" * 50)
        for i in range(len(monitor_types)):
            print(f"{i+1}. {monitor_types[i].get('name', 'N/A')} - {monitor_types[i].get('description', 'N/A')}")
        print("=" * 50)
        # Show current monitor type
        print(f"Current monitor type: {monitor.get('monitor_type', 'N/A')}")
        print("Press Enter to keep current monitor type")
        input_monitor_type = input("Enter new monitor type: ")
        if input_monitor_type.strip() != "":
            monitor["monitor_type"] = monitor_types[int(input_monitor_type)-1].get("name", "N/A")
    
        # If monitor type is periodic_upload or periodic_download, then prompt for period
        # Always populate monitor["config"]["period"]
        # Finally, check if period has a valid suffix and fix if required
        monitor_type = monitor.get("monitor_type", "N/A")
        if monitor_type in ["periodic_upload", "periodic_download"]:
            # Get current period  from monitor config
            config = monitor.get("config", {})
            current_period = config.get("period", "N/A")
            if "period" in config.keys():
                while True:
                    print(f"Current period: {current_period}")
                    print("Press Enter to keep current period")
                    input_period = input("Enter period: ")
                    if input_period.strip() == "":
                        monitor["config"]["period"] = current_period
                        break
                    # Check if input_period is valid
                    # Valid examples: 10, 10m, 10h, 10d
                    if not self._is_period_valid(input_period):
                        print(f"Invalid period: {input_period}. Please try again.")
                        continue

                    monitor["config"]["period"] = input_period
                    break
            else:
                # Get the period
                while True:
                    print(f"Period is in minutes(m), hours(h) or days(d). Default is minutes. For example 10m means 10 minutes.")
                    input_period = input("Please enter period: ").strip()
                    if input_period == "":
                        print("Period cannot be just spaces")
                        continue

                    # Check if input_period is valid
                    # Valid examples: 10, 10m, 10h, 10d
                    if not self._is_period_valid(input_period):
                        print(f"Invalid period: {input_period}. Please try again.")
                        continue

                    monitor["config"]["period"] = input_period
                    break
            
            # If input period has no "m", "h" or "d" , then suffix with "m"
            period = monitor["config"]["period"]
            if period.isdigit():
                monitor["config"]["period"] = period + "m"
            else:
                monitor["config"]["period"] = period
        elif monitor_type in ["run_command"]:
            # Handle run_command specific logic here
            # Get current command from monitor config
            config = monitor.get("config", {})
            current_command = config.get("command", "N/A")
            while True:
                if current_command == "N/A":
                    input_command = input("Enter command: ")
                    if input_command.strip() == "":
                        print("Command cannot be just spaces")
                        continue
                    monitor["config"]["command"] = input_command
                else:
                    print(f"Current command: {current_command}")
                    print("Press Enter to keep current command")
                    input_command = input("Enter command: ")
                    if input_command.strip() == "":
                        # Keep current command
                        monitor["config"]["command"] = current_command
                        break
                    monitor["config"]["command"] = input_command
                    break

        # Handle monitor_profile_map updates here if needed
        # We handle this in two steps.
        # First show existing monitor_profile_map and ask if user wants to delete any existing mappings
        # Then show all profiles and ask if user wants to add new mappings

        # Get existing monitor_profile_map for this monitor
        monitor_profiles = self.sqlite_handler.get_profiles_for_monitor(monitor_id=monitor_id)

        # Step 1: Handle deletion of existing monitor_profile_map
        if monitor_profiles:
            print("\nCurrent profiles linked to this monitor:")
            for profile in monitor_profiles:
                print(f"  - {profile.get('name', 'N/A')} (ID: {profile.get('id', 'N/A')})")
            
            # Ask if user wants to delete any profiles
            delete_profiles = {}
            for i, profile in enumerate(monitor_profiles):
                delete_profiles[i+1] = profile
            
            while delete_profiles:
                print("\nProfiles to delete (leave blank to skip):")
                for k, v in delete_profiles.items():
                    print(f"{k}. {v.get('name', 'N/A')}")
                
                input_delete_number = input("Enter profile number to delete (or press Enter to continue): ")
                if input_delete_number.strip() == "":
                    break
                
                if not input_delete_number.isdigit():
                    print(f"Invalid profile number: {input_delete_number}. Please try again.")
                    continue
                
                input_delete_number = int(input_delete_number)
                if input_delete_number not in delete_profiles.keys():
                    print(f"Invalid profile number: {input_delete_number}. Please try again.")
                    continue
                
                profile_to_delete = delete_profiles[input_delete_number]
                profile_id_to_delete = profile_to_delete.get('id', 0)
                
                # Delete the monitor_profile_map entry
                if self.sqlite_handler.delete_monitor_profile_map(
                    monitor_id=monitor_id,
                    profile_id=profile_id_to_delete
                ):
                    print(f"Profile '{profile_to_delete.get('name', 'N/A')}' removed from monitor")
                    monitor_profiles.remove(profile_to_delete)
                    del delete_profiles[input_delete_number]
                else:
                    print(f"Failed to remove profile '{profile_to_delete.get('name', 'N/A')}'")
                
                if not delete_profiles:
                    break

        # Step 2: Handle addition of new profiles
        # Get all available profiles
        all_profiles = self.sqlite_handler.get_profiles()
        
        # Build list of profiles not yet linked to this monitor
        current_profile_ids = {p.get('id') for p in monitor_profiles} if monitor_profiles else set()
        available_profiles = {}
        for i, profile in enumerate(all_profiles):
            if profile.get('id') not in current_profile_ids:
                available_profiles[i+1] = profile
        
        # Ask if user wants to add profiles
        if available_profiles:
            print("\nAvailable profiles to add:")
            while available_profiles:
                for k, v in available_profiles.items():
                    profile_name = v.get('name', 'N/A')
                    profile_type = v.get('profile_type', 'N/A')
                    print(f"{k}. profile name: {profile_name}, profile type: {profile_type}")
                
                input_add_number = input("Enter profile number to add (or press Enter to skip): ")
                if input_add_number.strip() == "":
                    break
                
                if not input_add_number.isdigit():
                    print(f"Invalid profile number: {input_add_number}. Please try again.")
                    continue
                
                input_add_number = int(input_add_number)
                if input_add_number not in available_profiles.keys():
                    print(f"Invalid profile number: {input_add_number}. Please try again.")
                    continue
                
                profile_to_add = available_profiles[input_add_number]
                profile_id_to_add = profile_to_add.get('id', 0)
                
                # Add the monitor_profile_map entry
                if self.sqlite_handler.add_monitor_profile_map(
                    monitor_id=monitor_id,
                    profile_id=profile_id_to_add
                ):
                    print(f"Profile '{profile_to_add.get('name', 'N/A')}' added to monitor")
                    current_profile_ids.add(profile_id_to_add)
                    del available_profiles[input_add_number]
                else:
                    print(f"Failed to add profile '{profile_to_add.get('name', 'N/A')}'")
                
                if not available_profiles:
                    print("All profiles have been added.")
                    break
                
                # Ask if user wants to add another profile
                input_continue = input("Do you want to add another profile? (Y/n): ")
                if input_continue.lower() == "y" or input_continue == "":
                    continue
                else:
                    break

        # Update monitor
        rowid = self.sqlite_handler.update_monitor(
            monitor_id=monitor.get("id", 0),
            name=monitor.get("name", "N/A"),
            monitor_path=monitor.get("monitor_path", "N/A"),
            remote_path=monitor.get("remote_path", "N/A"),
            monitor_type=monitor.get("monitor_type", "N/A"),
            config=monitor.get("config", {}),
            status=monitor.get("status", "stopped")
            )
        if rowid is not None:
            print(f"Monitor name: {monitor.get('name', 'N/A')} has been updated")
        else:
            print(f"Monitor name: {monitor.get('name', 'N/A')} has not been updated")

    def monitor_new(self):
        """
        Create new monitor
        """

        # Sanity check for profiles
        # If there are no profiles there is no point in prompting the user for a monitor configuratio
        profiles = self.sqlite_handler.get_profiles()
        if profiles is None or len(profiles) == 0:
            self.logger.warning(f"No profiles found in {self.sqlite_handler.db_path}")
            self.logger.warning(f"Please add profiles first")
            return
    
        # Prompt user for new monitor
        while True:
            print("Please enter monitor name")
            input_monitor_name = input("Enter monitor name: ")

            if input_monitor_name.strip() == "":
                print("Monitor name cannot be just spaces.")
                return
            
            print(f"You entered monitor name: {input_monitor_name}")

            # Check if monitor already exists
            monitor = self.sqlite_handler.get_monitor(monitor_name=input_monitor_name)

            if monitor:
                print(f"Monitor name: {input_monitor_name} already exists. Please try again")
                continue
            break

        # Monitor_path
        while True:
            input_monitor_path = input("Please enter monitor path: ")

            if input_monitor_path.strip() == "":
                print("monitor path cannot be just spaces.")
                return
            
            print(f"You entered monitor path: {input_monitor_path}")
            break
          
        # Remote_path
        while True:
            input_remote_path = input("Please enter remote path: ")

            if input_remote_path.strip() == "":
                print("Remote path cannot be just spaces.")
                return
            
            print(f"You entered remote path: {input_remote_path}")
            break

        # Get monitor types
        monitor_types = self.sqlite_handler.get_lookup_table(
            table_name="monitor_types"
        )

        if not monitor_types:
            print(f"No monitor types found in {self.sqlite_handler.db_path}")
            return

        while True:
            for i in range(len(monitor_types)):
                is_implemented = monitor_types[i]['implemented']
                if is_implemented: 
                    print(f"{i+1}. {monitor_types[i]['name']} - {monitor_types[i]['description']}")

            input_monitor_type_number = input("Please select number of monitor type: ")
            if input_monitor_type_number.strip() == "":
                print("Monitor type cannot be just spaces")

            if not input_monitor_type_number.isdigit():
                print(f"Invalid monitor type number: {input_monitor_type_number}. Please try again.")
                continue

            input_monitor_type_number = int(input_monitor_type_number)
            if input_monitor_type_number > 0 and input_monitor_type_number <= len(monitor_types):
                break
            
        print(f"You entered monitor type numer: {input_monitor_type_number}")
        monitor_type = monitor_types[input_monitor_type_number-1]["name"]
        print(f"You selected monitor type: {monitor_type}")
        if monitor_type == "periodic_upload" or monitor_type == "periodic_dowload":
            # Get the period
            while True:
                print(f"Period is in minutes(m), hours(h) or days(d). Default is minutes. For example 10m means 10 minutes.")
                input_period = input("Please enter period: ").strip()
                if input_period == "":
                    print("Period cannot be just spaces")
                    continue

                # Check if input_period is valid
                # Valid examples: 10, 10m, 10h, 10d
                if not self._is_period_valid(input_period):
                    print(f"Invalid period: {input_period}. Please try again.")
                    continue
                break
            
            # If input period has no "m", "h" or "d" , then suffix with "m"
            if input_period.isdigit():
                input_period = input_period + "m"

            monitor_config = {
                "period": input_period
            }
        elif monitor_type == "run_command":
            # Get the command to run
            while True:
                input_command = input("Please enter command to run: ").strip()
                if input_command == "":
                    print("Command cannot be just spaces")
                    continue
                break

            monitor_config = {
                "command": input_command
            }
        else:
            monitor_config = {}

        # Now link the monitor to one or more profiles
        # A monitor can be linked to any profile type.
        # The monitor handler is determined at runtime based on the profile-type

        # Use must select at least 1 profile
        selected_profiles = []
        # Build list of unselected profiles
        unselected_profiles: dict[int, Any] = {}
        for i, p in enumerate(profiles):
            profile_name = p.get("name", "N/A")
            profile_type = p.get("profile_type", "N/A")
            unselected_profiles[i+1] = p

        while True:
            # Stop if all profiles have been selected
            if not unselected_profiles:
                print("All profiles have been selected.")
                break

            print("Profiles:")
            for k,v in unselected_profiles.items():
                profile_name = v.get("name", "N/A")
                profile_type = v.get("profile_type", "N/A")
                print(f"{k}. profile name: {profile_name}, profile type: {profile_type}")
            
            input_profile_number = input("Please select profile number: ")
            if input_profile_number.strip() == "":
                print("Profile cannot be just spaces")
                continue

            if not input_profile_number.isdigit():
                print(f"Invalid profile number: {input_profile_number}. Please try again.")
                continue

            input_profile_number = int(input_profile_number)
            if input_profile_number not in unselected_profiles.keys():
                print(f"You entered an invalid profile number: {input_profile_number}")
                continue
            
            print(f"You entered profile number: {input_profile_number}")
            chosen = unselected_profiles[input_profile_number]
            selected_profiles.append(chosen)

            # Remove chosen profile from unselected_profiles
            del unselected_profiles[input_profile_number]
            # If all profiles are now selected, stop automatically
            if len(unselected_profiles) == 0:
                print("All profiles have been selected.")
                break

            # Want to add another profile ?
            input_continue = input("Do you want to add another profile ? (Y/n): ")
            if input_continue.lower() == "y" or input_continue == "":
                continue
            else:
                break


        # Create monitor
        monitor_id = self.sqlite_handler.add_monitor(
            name=input_monitor_name,
            monitor_path=input_monitor_path,
            remote_path=input_remote_path,
            monitor_type=monitor_types[input_monitor_type_number-1]["name"],
            config=monitor_config,
            status="stopped"
            )

        if monitor_id is None:
            print(f"Monitor name: {input_monitor_name} not created")
            return
        else:
            print(f"Monitor name: {input_monitor_name} created")
            # For every selected profile create monitor_profile_map records
            for i in range(len(selected_profiles)):
                profile = selected_profiles[i]
                profile_id = profile["id"]
                self.sqlite_handler.add_monitor_profile_map(
                    monitor_id=monitor_id,
                    profile_id=profile_id
                )

    def monitor_test(self):
        """
        Test monitor
        """

        monitors = self.sqlite_handler.get_monitors()
        if not monitors:
            print(f"No monitors found in {self.sqlite_handler.db_path}")
            return
        
        while True:
            # Show all monitors
            print("\nList of monitors")
            print("=" * 50)
            print("0.  Select all monitors")
            for i in range(len(monitors)):
                print(f"{i+1}. {monitors[i].get('name', 'N/A')}")
            print("=" * 50)
            input_monitor_number = input("Enter monitor number: ")
            if input_monitor_number == "":
                print("Nothing selected")
                return

            if input_monitor_number == "0":
                break

            # Check if input_monitor_number is numeric
            if not input_monitor_number.isdigit():
                print(f"Invalid monitor number: {input_monitor_number}. Please try again.")
                continue

            input_monitor_number = int(input_monitor_number)    
            # Check if input_monitor_number is in valid range
            if input_monitor_number > 0 and input_monitor_number <= len(monitors):
                break
            else:
                print(f"Invalid monitor number: {input_monitor_number}. Please try again.")

        if input_monitor_number == "0":
            print("Your selected all monitors")
            monitor_id = None
        else:
            monitor = monitors[input_monitor_number-1]
            monitor_id = monitor.get("id", "N/A")

        try:
            diagnostic_util = DiagnosticUtil(
                db_path=self.db_path,
                logger=self.logger)

            if not diagnostic_util.check_monitor_config(monitor_id=monitor_id):
                return
        finally:
            print("Monitor test completed")


    def config_test(self):
        """
        Test configuration
        """
        try:
            diagnostic_util = DiagnosticUtil(
                db_path=self.db_path,
                logger=self.logger)
            if (not diagnostic_util.check_app_env()):
                return

            diagnostic_util.check_profile_import()
            if not diagnostic_util.check_rclone_dependency():
                return

            if not diagnostic_util.check_monitor_config():
                return
            
            diagnostic_util.print_overview()
            return
        finally:
            print("Exiting test mode now")

    def config_file(self):
        """
        Print location of SQLite database
        """
        
        print(f"Location of SQLite database: {self.db_path}")


    def _select_profile(self) -> dict[str, Any]:
        """
        Show all profiles and let user choose one
        Return profile as dictionary
        """

        # Get all profiles
        profiles : list[dict[str, Any]] = self.sqlite_handler.get_profiles()
        if profiles is None or len(profiles) == 0:
            print(f"No profiles found in {self.sqlite_handler.db_path}")
            return {}
        
        while True:
            # Show all profiles
            profile_ids : list[int] = []
            profile_id_entered : str = ""
            profile : dict[str, Any] = {}
            for profile in profiles:
                profile_id = profile.get("id", "N/A")
                profile_ids.append(profile_id)
                profile_name = profile.get("name", "N/A")
                print(f"Id: {profile_id}, Profile name: {profile_name}")
                # Prompt user for profile_id
                profile_id_entered = input("Enter profile id: ")
                print(f"You entered profile id: {profile_id_entered}")
                if not profile_id_entered.isdigit():
                    print(f"Invalid profile id: {profile_id_entered}. Please try again.")
                    continue
                profile_id = int(profile_id_entered)
                if profile_id not in profile_ids:
                    print(f"Invalid profile id: {profile_id}. Please try again.")
                    continue
                break   # for
            break   # while

        return profile

    def profile_test(self, profile_id: int | None = None):
        """
        Test selected profile
        """

        if profile_id:
            # Get profile from database using sqlite handler
            profile = self.sqlite_handler.get_profile(profile_id=profile_id)
            if profile is None:
                print(f"Profile not found: {profile_id}")
                return
        else:
            profile = self._select_profile()
            if not profile:
                return
            
        print(f"You selected profile id: {profile_id}")
        print(f"You selected profile name: {profile.get('name', 'N/A')}")
        # Get profile from database using sqlite handler
        profile = self.sqlite_handler.get_profile(profile_id=profile_id)
        if profile is None:
            print(f"Profile not found: {profile_id}")
            return
        
        # Derive base handler from handler in config in profile
        config = profile.get("config", {})
        handler = config.get("handler")

        if handler is None or handler.strip() == "" or handler.strip().lower() == "foldermonitor":
            # The default handler is foldermonitor, which at present means the profile is for testing connectivity to an S3 compatible service
            # Get s3_client from S3ConnectionFactory
            s3_factory = S3Factory(
                logger=self.logger
            )

            s3_client = s3_factory.get_s3_client(profile_config=config)
            # Get bucket list using s3_client
            try:
                buckets = s3_client.list_buckets()
                if buckets is None or 'Buckets' not in buckets:
                    print(f"No buckets found on remote profile name: {profile_id}")
                else:
                    print("Buckets:")
                    for bucket in buckets["Buckets"]:
                        print(f"Bucket: {bucket}")

            except ClientError as e:
                error_code = e.response.get('Error', {}).get('Code')
                if error_code == 'AccessDenied':
                    print("Connection successful! (ListBuckets permission denied).")
                    print("Your credentials are valid, but restricted.")
                else:
                    print(f"Error: {e}")
                    print(f"Test for profile '{profile_id}' failed")
                    return
            except Exception as e:
                print(f"Error: {e}")
                print(f"Test for profile '{profile_id}' failed")
                return
            else:
                print(f"Test for profile '{profile_id}' successful")
        elif handler.strip().lower() == "rclone":
            # The handler is rclone, which means we will test connectivity using rclone
            profile_name = profile.get("name")
            if profile_name is None:
                print(f"Profile name not found for profile id: {profile_id}")
                return
            base_remote_path = f"{profile_name}:"
            rclone_handler = RcloneHandler(
                logger=self.logger,
                base_source_path="profile_test_temp_source",
                base_remote_path=base_remote_path,
                profile_name=profile_name
            )

            # Test connectivity by running lsd command
            try:
                rclone_parms = ["lsd"]
                (result_code, result_output) = rclone_handler.run_command(
                    rclone_parms=rclone_parms
                )
                if result_code == 0:
                    # Check if output contains: failed to create file system 
                    if "failed to create file system" in result_output.lower():
                        print(f"Connection failed to remote profile name: {profile_name}")
                        print(f"Error output: {result_output}")
                    else:
                        print(f"Connection successful to remote profile name: {profile_name}")
                        print(f"Output: {result_output}")
                else:
                    print(f"Connection failed to remote profile name: {profile_name}")
                    print(f"Error output: {result_output}")
                    print(f"Test for profile '{profile_id}' failed")
                    return
            except Exception as e:
                print(f"Connection failed to remote profile name: {profile_name}")
                print(f"Error: {e}")
        else:
            print(f"Unknown handler: {handler}")
            print(f"Test for profile '{profile_id}' failed")

        return

      
    def profile_delete(self):
        """
        Show all profiles and let user choose one to delete
        """

        # Show all profiles
        profiles = self.sqlite_handler.get_profiles()
        if profiles is None or len(profiles) == 0:
            self.logger.info(f"No profiles found in {self.sqlite_handler.db_path}")
            return

        profile_names = []
        for profile in profiles:
            profile_name = profile.get("name", "N/A")
            profile_names.append(profile_name)

        # Show all profiles
        print("\nList of profiles to delete")
        print("=" * 50)
        for i in range(len(profile_names)):
            print(f"{i+1}. {profile_names[i]}")
        print("=" * 50)

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

        if self.sqlite_handler.delete_profile(profile_name=profile_name):
            print(f"Profile name: {profile_name} deleted")
        else:
            print(f"Profile name: {profile_name} not deleted")

    def profile_edit(self):
        """
        Show all profiles and let user choose one to edit
        """

        implemented_profiles = self.sqlite_handler.get_implemented_profiles()
        # If there are no implemented_profiles then we are done
        if not implemented_profiles:
            print(f"No implemented profiles found in {self.sqlite_handler.db_path}")
            return
        
        while True:
            # Show all implemented profiles
            for i in range(len(implemented_profiles)):
                print(f"{i+1}. {implemented_profiles[i].get('name', 'N/A')}")

            input_profile_index = input("Enter profile number: ")

            if input_profile_index == "":
                print("No profile selected")
                return

            print(f"You entered profile number: {input_profile_index}")
            if input_profile_index.strip() == "": # User entered Enter
                print("No profile selected")
                return
            
            if input_profile_index.isdigit():
                input_profile_index = int(input_profile_index)
                if input_profile_index > 0 and input_profile_index <= len(implemented_profiles):
                    break

            print(f"Invalid profile number: {input_profile_index}. Please try again.")

        # Get profile name
        input_profile_index = int(input_profile_index)
        profile = implemented_profiles[input_profile_index-1]
        input_profile_name = profile.get("name", "N/A")
        print(f"You selected profile: {input_profile_name}")

        profile_config = profile.get("config", {})
        current_provider_id = profile_config.get("provider_id", "0")

        # Lookup current provider 
        current_provider = self.sqlite_handler.get_provider(provider_id=current_provider_id)
        if not current_provider:
            print(f"Provider not found for profile: {input_profile_name}")
            return

        # At this point we have a valid profile_type, provider_id and provider_name
        # Currently we have only profile_type s3 implemented
        # When other profile types are implemented we need to change the logic here
        # Show current access key
        current_profile_access_key = profile_config.get("access_key_id", "N/A")
        print(f"Press Enter to keep current S3 access key: : {current_profile_access_key}")
        # Prompt user for access key
        input_access_key_id = input(f"Enter S3 access key id of your provider: {current_provider.get('name', 'N/A')}: ")
        if input_access_key_id.strip() != "":
            # Store access key in profile_config
            profile_config["access_key_id"] = input_access_key_id

        # Show current secret key
        current_secret_key = profile_config.get("access_key_secret", "N/A")
        print(f"Press Enter to continue with S3 access key secret: {current_secret_key}")
        # Prompt user for secret key
        input_access_key_id_secret = input("Please enter secret key: ")
        if input_access_key_id_secret.strip() != "":
            # Store secret key in profile_config
            profile_config["access_key_secret"] = input_access_key_id_secret

        # Prompt user for region
        # For Amazon we need the region
        provider_name = profile_config.get("provider_name", "N/A")
        if "Amazon AWS" in provider_name:
            profile_config["env_auth"] = "false"
            profile_region = profile_config.get("region", None)
            while True:
                # Show current region
                if profile_region:
                    print(f"Press Enter to continue with current region: {profile_region}")
                    # Prompt user for region
                    input_profile_region = input(f"Enter S3 region of your provider: {provider_name}: ")
                    if input_profile_region.strip()  == "":
                        # No changes in profile_config
                        break
                    # Update region in profile_config
                    profile_config["region"] = input_profile_region
                    break
                else:
                    # Prompt user for region
                    input_profile_region = input(f"Enter S3 region of your provider: {provider_name}: ")
                    if input_profile_region.strip()  == "":
                        print("Region cannot be just spaces. Please try again.")
                        continue

                    # Update region in profile_config
                    profile_config["region"] = input_profile_region
                    break
        else:
            # For other providers we need the endpoint
            current_endpoint = profile_config.get("endpoint", "N/A")
            print(f"Press Enter to keep current endpoint: {current_endpoint}")
            while True:
                if current_endpoint:
                    input_profile_endpoint = input(f"Enter S3 endpoint from your provider: {provider_name}: ")
                    if input_profile_endpoint.strip() != "":
                        # Update endpoint in profile_config
                        profile_config["endpoint"] = input_profile_endpoint
                    break
                else:
                    input_profile_endpoint = input(f"Enter S3 endpoint of your provider: {provider_name}: ")
                    if input_profile_endpoint.strip() == "":
                        print("Endpoint cannot be just spaces. Please try again.")
                        continue
                    # Update endpoint in profile_config
                    profile_config["endpoint"] = input_profile_endpoint
                    break

        # Profile_config has already been populated with provider_id, provider_name, access_key_is etc
        # Now update profile
        if self.sqlite_handler.update_profile(
            profile_id=profile["id"],
            name=profile["name"],
            profile_type=profile["profile_type"],
            config=profile_config
            ):
            print(f"Profile name: {input_profile_name} updated")
        else:
            print(f"Profile name: {input_profile_name} not updated")

        print("Please test profile with one of the following commands:")
        print(f"   Windows command: folder_monitor.exe profile test")
        print(f"   Linux or Windows command: python folder_monitor.py profile test")


    def profile_new(self):
        """
        Create new profile
        """

        implemented_providers = self.sqlite_handler.get_implemented_providers()
        if not implemented_providers:
            print("No implemented providers found")
            return
        
        # Prompt user for profile_name
        while True:
            print("Please enter profile name of S3 cloud storage. You can get the reference on the website of provider: ")
            input_profile_name = input("Enter profile name: ")

            if input_profile_name.strip() == "":
                print("Profile name cannot be just spaces.")
                return
            
            print(f"You entered profile name: {input_profile_name}")

            # Check if profile_name already exists
            profile = self.sqlite_handler.get_profile(profile_name=input_profile_name)

            if profile:
                print(f"Profile name: {input_profile_name} already exists. Please try again")
                continue
            break

        # Get user to select a provider
        while True:
            print("Enter provider number")
            for i in range(len(implemented_providers)):
                provider = implemented_providers[i]
                print(f"{i+1}. {provider['name']}")
            input_provider_number = input("Enter provider number: ")

            if input_provider_number == "":
                print("No provider selected")
                return

            print(f"You entered provider number: {input_provider_number}")
            if input_provider_number.isdigit():
                input_provider_number = int(input_provider_number)
                if input_provider_number > 0 and input_provider_number <= len(implemented_providers):
                    break
            else:
                print(f"Invalid provider number: {input_provider_number}. Please try again.")
                continue
            break

        input_provider_id = implemented_providers[input_provider_number-1]["id"] or "0"
        input_provider_name = implemented_providers[input_provider_number-1]["name"] or "N/A"
        input_type_name = implemented_providers[input_provider_number-1]["profile_type"] or "N/A"

        # Prompt user for access key
        while True:
            input_access_key_id = input(f"Enter S3 access key id of your provider: {input_provider_name}: ")
            print(f"You entered access key: {input_access_key_id}")
            if input_access_key_id.strip() == "":
                print("Access key id cannot be empty. Please try again.")
                continue
            break

        # Prompt user for secret key
        while True:
            input_access_key_id_secret = input(f"Enter S3 access secret key of your provider: {input_provider_name}: ")
            print(f"You entered access key: {input_access_key_id_secret}")
            if input_access_key_id.strip() == "":
                print("Access secret key cannot be empty. Please try again.")
                continue
            break

        input_region = None
        input_endpoint = None
        if "Amazon AWS" in input_provider_name:
            while True:
                input_region = input(f"Enter S3 region of your provider: {input_provider_name}: ")
                print(f"You entered region: {input_region}")
                if input_region.strip() == "":
                    print("Region cannot be empty. Please try again.")
                    continue
                break
        else:
            while True:
                input_endpoint = input(f"Enter S3 endpoint from your provider: {input_provider_name}: ")
                print(f"You entered endpoint: {input_endpoint}")
                if input_endpoint.strip() == "":
                    print("Endpoint cannot be empty. Please try again.")
                    continue
                break

        # Create profile
        profile_config = {
            "provider_id": input_provider_id,
            "provider_name": input_provider_name,
            "access_key_id": input_access_key_id,
            "access_key_secret": input_access_key_id_secret,
        }

        if "Amazon AWS" in input_provider_name:
            profile_config["env_auth"] = "false"
            profile_config["region"] = input_region
        else:
            profile_config["endpoint"] = input_endpoint

        # Now add profile to database
        profile_id = self.sqlite_handler.add_profile(
            name=input_profile_name,
            profile_type=input_type_name,
            config=profile_config
            )

        if profile_id is None:
            print(f"Profile name: {input_profile_name} not created")
        else:
            print(f"Profile name: {input_profile_name} created")

        print("Please test profile with one of the following commands:")
        print(f"   Windows command: folder_monitor.exe profile test")
        print(f"   Linux or Windows command: python folder_monitor.py profile test")


    def profile_show(self):
        """
        Show all profiles
        """

        # Show all profiles
        profiles = self.sqlite_handler.get_profiles()
        for profile in profiles:
            print("=" * 50)
            print(f"Profile name: {profile.get('name', 'N/A')}")
            print(f"Profile type: {profile.get('profile_type', 'N/A')}")
            config = profile.get("config", {})
            for key in config:
                print(f"   {key}: {config[key]}")   


    def profile_import(self):
        """
        Import profiles from rclone
        """
        self.diagnostic_util.check_profile_import()
