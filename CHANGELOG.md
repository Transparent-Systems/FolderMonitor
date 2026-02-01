# Changelog

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
