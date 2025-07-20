@echo off
:: Backup the current folder to the e2 remote using rclone
setlocal

:: Define the source and destination
set SOURCE=D:\Development\FolderMonitor
set DESTINATION=e2:/development-zoetebier-net/Development/FolderMonitor

:: Run the rclone copy command
rclone sync "%SOURCE%" "%DESTINATION%" --progress --exclude  ".venv/**"

:: Check for errors
if %ERRORLEVEL% neq 0 (
    echo Backup failed!
    exit /b %ERRORLEVEL%
) else (
    echo Sync completed successfully!
)

endlocal