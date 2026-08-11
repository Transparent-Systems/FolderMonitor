# Release Notes FolderMonitor

## [2.0.0] - 2026-02-15

- Added Python S3Handler. 
    This is a native Python handler that handles requests to S3 storage providers.  
    Having a native S3 handler eliminates the need for Rclone for S3 compatible cloud storage providers, like:
    - Amazon S3
    - Cloudflare R2
    - IDrive E2
    - Backblaze B2
    - Alibaba Cloud OSS
 
    Processing changes of many small files is between 2 - 3 times faster with S3Handler.
    For files of about 1Mb the data transfer is a fraction faster with S3Handler.  
    FolderMonitor will use S3Handler if the remote profile is in foldermonitor.conf  
    You can import the S3 profiles from Rclone  with command:  
    - python folder_monitor.py profile import  

    Any remote profile not in foldermonitor.conf will use Rclone.  
- Added fault tolerance to remote storage.
    This is impleented by connecting one monitor to multiple remote storage providers.  
    Changes to a monitor path are propagated to all remote storage providers configured in remote_profiles.  
    If the connection to one providers is interrupted the data still propagate to the other remote storage providers. 
    Adding another remote provider is as simple as adding a remote profile.  
    An example configuration of multiple remotes is included in conf.example.yaml  
- Added command processor
    There are now commands for configuration and remote profile life cycle.
    To get help type:  
    - python folder_monitor.py -h
    - python folder_monitor.py profile -h
    - python folder_monitor.py config -h
- Removed property remote_profile from monitor configuration.
- Removed testing configuration from YAML configuration
    The testing configuration is for developers only, not for end users.


## v1.3.0 - Removed backup copy mode

Removed mode from backup configuration.
Now a backup only runs on copy mode, i.e backup will never delete a file at destination.
This is the safest method and avoids surprises.
For example a laptop may have only a few folders with pictures while the entire collection is in cloud storage.
Next, running in backup sync mode may remove all other picture folder from cloud storage.

## v1.2.0 - Enhanced Configuration & Safety Checks

Build foldermonitor.exe executable


## v1.1.0 - Enhanced Configuration & Safety Checks

### ✨ New Features

This release focuses on user experience and error prevention.

* **Monitor Path:** Check if monitor path exists
* **Connectivity Test:** Performs a test copy via `rclone` to verify destination availability.


## v1.0.0 - first release

Initial release of Folder Monitor.
This release has been tested on Windows 11 and Linux (Ubuntu 22.04)

### ⚠️ Prerequisites

Before running script `python folder_monitor.py` ), ensure you have:
1. **rclone** installed and configured in your system PATH.
2. Run the two check scripts included in the repository to initialize your environment.

    ```bash
    python check-env.py
    python check_config.py --config-path "./conf/config.yaml"
    ```

