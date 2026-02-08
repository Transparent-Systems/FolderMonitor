# Changelog

## [2.0.0] - 2026-02-10

- Added Python S3Handler.  
    The S3Handler is a native Python handler that handles requests to S3 storage providers.  
    Having a native S3 handler eliminates the need for Rclone for S3 compatible cloud storage providers, like:
    - Amazon S3
    - Cloudflare R2
    - Idrive E2
    - Backblaze B2
    - Alibaba Cloud OSS

- Added CommandProcessor
    The Command Processor handles commands like verson, test, profile, config and their subcommands and parameters
- Added remote_profiles to YAML configuration
    This allows a monitor to be propagates to one or more cloud providers at the same time.  
    This adds fault tolerance to a monitor in case a connection to one of the cloud providers is lost.  
- Removed remote_profile from YAML configuration
- Removed testing configuration from YAML example as testing configuration is for development purposes only

## [1.3.0] - 2026-02-01

Removed mode from backup configuration.
Now a backup only runs on copy mode, i.e backup will never delete a file at destination.

## [1.2.0] - 2026-01-26

- Create exe file with PyInstaller
- Moved checks from check-env.py and check_config.py to folder_monitor.py
- Changed argument --config-path to --config
- Added short arguments for folder_monitor.py: -c (--config) and -t (--test)

## [1.1.0] - 2026-01-25

- Check monitor path exist.
- Check rclone can copy a temporary file to the destination path

## [1.0.0] - 2026-01-19

- Initial release of FolderMonitor.
- This release has been tested on Windows 11 and Linux (Ubuntu 22.04).
- MIT License
