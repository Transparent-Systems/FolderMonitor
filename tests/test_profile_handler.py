# Add the scripts directory to the Python path
from pathlib import Path
import sys

scriptspath = Path(__file__).parent / Path("../scripts")
sys.path.insert(0, scriptspath.resolve().as_posix())

try:
    from profile_handler import ProfileHandler
except ModuleNotFoundError:
    from scripts.profile_handler import ProfileHandler

def test_update_profile(profile_name: str = None):
    print("Start testing ProfileHandler")
    profile_handler = ProfileHandler(
        app_name="foldermonitor",
        config_name="foldermonitor.test.conf"
    )

    # Print config path
    print(f"Config path: {profile_handler.config_path}")

    # Get profile names
    profile_names = profile_handler.get_profile_names()
    # Printing profile names
    if (profile_names is None or len(profile_names) == 0):
        print(f"No profiles found in {profile_handler.config_path}")
    else:
        for profile_name in profile_names:
            print(f"Profile name: {profile_name}")

    if profile_name is None:
        profile_name = "test-update-profile"

    # Create profile dictionary
    test_profile = {
        "type": "s3",
        "access_key_id" : "<my_access_key_id>",
        "access_key_secret": "<my_access_key_secret>",
        "default_region": "us-east-1",
        "key1": "value1",
        "key2": "value2",
        "key3": "value3"
    }

    # Get profile
    if (profile_handler.get_profile(profile_name=profile_name)):
        # Update profile
        if (not profile_handler.update_profile(
            profile_name=profile_name,
            profile=test_profile)
            ):
            print(f"Error updating profile: {test_profile['profile_name']}")
    else:
        # Add a profile
        if (not profile_handler.add_profile(
            profile_name=profile_name,
            profile=test_profile)):
            print(f"Error adding profile: {test_profile['profile_name']}")

    profile = profile_handler.get_profile(profile_name=profile_name)
    print(f"Profile name: {profile_name}")
    # Print key, value of profile
    for key, value in profile_handler.get_profile(profile_name=profile_name).items():
        print(f"{key}: {value}")

    # Add a few new attributes and remove some 
    test_profile = {
        "type": "s3",
        "provider": "Amazon AWS",
        "access_key_id" : "<my_access_key_id>",
        "access_key_secret": "<my_access_key_secret>",
        "region": "us-east-1",
        "key4": "value1",
        "key5": "value2",
        "key6": "value3"
    }

    # Update profile
    if profile_handler.update_profile(
        profile_name=profile_name,
        profile=test_profile):
        print(f"Profile name: {profile_name}")
        # Print key, value of profile
        profile = profile_handler.get_profile(profile_name=profile_name)
        for key in profile:
            print(f"{key}: {profile[key]}")
    else:
        print(f"Error updating profile: {profile_name}")

    print("End test update profile")


def test_create_profile(profile_name: str):
    print("Begin test_create_profile")
    profile_handler = ProfileHandler(
        app_name="foldermonitor",
        config_name="foldermonitor.test.conf"
    )

    # Create profile dictionary
    test_profile = {
        "test_name": "test_create_profile",
        "type": "s3",
        "access_key_id" : "<my_access_key_id>",
        "access_key_secret": "<my_access_key_secret>",
        "s3_default_region": "us-east-1",
        "key1": "value1",
        "key2": "value2",
        "key3": "value3"
    }

    if profile_name is None:
        profile_name = "test-create-profile"

    # Get profile
    if (profile_handler.get_profile(profile_name=profile_name)):
        # Update profile
        if (not profile_handler.update_profile(
            profile_name=profile_name,
            profile=test_profile)
            ):
            print(f"Error updating profile: {test_profile['profile_name']}")
    else:
        # Add a profile
        if (not profile_handler.add_profile(
            profile_name=profile_name,
            profile=test_profile)):
            print(f"Error adding profile: {test_profile['profile_name']}")
    print("End testing test_create_profile")

def test_delete_profile(profile_name: str):
    print("Begin test_create_profile")
    profile_handler = ProfileHandler(
        app_name="foldermonitor",
        config_name="foldermonitor.test.conf"
    )


    # Get profile
    if (not profile_handler.get_profile(profile_name=profile_name)):
        print("Profile name {profile_name} not found")
        return False

    # Delete profile
    if (not profile_handler.delete_profile(
        profile_name=profile_name)):
        print(f"Error deleting profile: {profile_name}")
        return False
    
    return True

if __name__ == '__main__':
    # test_update_profile("test-update-profile")
    # test_create_profile("test-create-profile")
    test_create_profile("test-create-profile-2")
    # test_delete_profile("test-create-profile-2")
