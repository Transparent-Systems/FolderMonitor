
<img src="https://tsl003-aip.zoetebier.net/wp-content/uploads/2025/06/AIP_grey_transparent_background_github-e1750625832556.png" alt="AIP logo">

[Website](https://tsl003-aip.zoetebier.net) |
[Documentation](https://tsl003-aip.zoetebier.net/foldermonitor/) |


# FolderMonitor

FolderMonitor monitors a folder for changes and propagest thos changes to a target destination.  
The target destination is usually a cloud storage provider like iDrive, BackBlaze, Amazon S3 or Google Drive.  
Examples of other targets are a shared drive, a local drive or an FTP share.  
FolderMonitor uses rclone as a tool to propagate changes.

## Requirements

| Requirement | Version | Comment |
|---|---|---|
| rclone | >= v1.64.2 | See: https://rclone.org/ |
| Python | >= 3.13.0  | See: https://www.python.org/ |  
| watchog | >= 6.0.0  | Python module. Version is in requirements.txt |  
| PyYAML | >= 6.0.2   | Python module. Version is in requirements.txt |  

## Features

  * folder_monitor.py  
    This is the core script that monitors a folder for changes and propagates changes to the destination.  
    Call example:  
      python folder_monitor.py --monitor-path "D:/Cloud/Test" --base-path "Cloud" --destination-path "e2:test-foldermonitor/Cloud" --sync-mode True
  * folder_monitor_batch.py  
    This script allows you to start one or more monitors in one go.  
    It is very convenient to use this script in a job scheduler like TaskScheduler to start a bunch of monitors in one go.
    Otherwise you would have to start a separate job for each monitor.
    Every monitor is a line in text file monitor_entries.txt
    The format is exactly the same as the parameters of script folder_monitor.py
  * Folder_copy  
    Folder_copy allows you to test an entry from file monitor_entries.txt
    That way you can test each monitor individually before running folder_monitor_batch.py
  * Logging  
    Each script logs to the command line and to a rotating log file.
    Log properties are configured on YAML file monitor.yaml

## Installation & documentation
| Application or module | How to install |
|---|---|
| rclone | Download from https://rclone.org/downloads/ |
| Python | Download from https://rclone.org/downloads/ |
| FolderMonitor | Download ZIP file from GitHub or git clone the repository  |
| watchog | Use pip installer. See below |
| PyYAML | Use pip installer. See below |

Notes:  
I recommend to download and install rclone and Python from their official download locations.
If you instal from the Windows store or using Winget you may not get all components.

First install Python if required. Next install the required Python modules using pip.
For example FolderMonitor folder is C:\Apps\FolderMonitor
Open a command shell or powershell.
Go to folder C:\Apps\FolderMonitor
Type: pip install -r scripts/requirements.txt

If you have more than one Python applications on your PC, it is best practice to create a virtual Python environment.
This avoids version conflicts when running different Python applications.
Each Python virtual environment is isolated from another virtual environment.
A Python virtual environment is implemented in a folder with all Python files required to run a particular Python application.
Instructions are in FolderMonitor Python scripts and copied here for convenience.

- It is recommended to use a virtual Python environment to avoid conflicts with other packages.
- To create and activate a virtual environment:  
    python -m venv .venv  
    .\.venv\Scripts\Activate.ps1  (Windows)  
    source .venv/bin/activate  (macOS/Linux)  
- After Python has been installed you can install required modules with:  
    pip install -r scripts/requirements.txt  

## License
This is free software under the terms of the MIT license included in this package.  
See file: COPYING.txt


## Why FolderMonitor
You can find more information at: https://tsl003-aip.zoetebier.net/foldermonitor/

Project FolderMonitor grew organically over time as I tried to find solutions for issues I encountered while working on my PCs and servers.  
Initially I used OneDrive to "backup" files to the OneDrive cloud storage.  
However with several file explorers running simulteneously the PC became unresponsive.  
OneDrive was frequently using 100% CPU making working on the PC impossible.
This was a deal breaker to me, I uninstalled OneDrive and decided to use rclone for copying files to the cloud.  

Rclone worked a lot better than OneDrive and worked unobtrusive in the background.  
I ran an rclone job every few hours and this was just fine for my purposes.  
Until one day I wanted to upload my security videos to the cloud as well.  
It was critical to upload those videos instantly and build a simple PowerShell script to do the job.  
It worked, but it was not scalable. Each time I wanted to monitor another folder I had to copy the script and change the settings.
The loggin was cumersome as well and I needed to run a separate cleanup job for the log files generated.
The main issues was that PowerShell was running on Windows only.  

Now I had the choice to build a separate application for Linux, or build a generic solution for Windows, Linux and Mac OS.  
This is when FolderMonitor was born.  
It's a Python application that depends on only a few components: rclone and watchdog.  
While I had little expereince with Python, it has proven to be a great choice.  
VS Code has fantastic support for Python development like code completion and debugging.  

I installed GitHub Copilot extension for code generation and suggestions.  
In addition I used Google Gemini to chat outside VS Code. This worked just great.  
This setup allowed me to get a different perspective and alternative solutions.  

## Future development
It is difficult to predict the future and what it measn for FolderMonitor.
Future deelopment depends on community support and request coming from the community.

Some new features could include:
- Adding a delay timer before changes are propagated.    
  This basically turns FolderMonitor into a dedicated taks scheduler to propagate file changes.  
  This avoids the need to configure a job in TaskScheduler (Windows) or Cron (Linux)
- A security tool.  
  Monitoring changes of files and folders could trigger an alarm, like email, SMS message or a Discours event.
- Trigger a CI/CD job
- Develop a GUI to configure and start a monitor
- Bundle the scripts into an application to facilitate application setup for non-technical users.
  Some packaging and installation candidates are:
  - PyInstaller
  - cx_Freeze
  - Briefcase
  - Pip
  - Conda

  Each of these packaging tools have their pros and cons.  

The main reason for a monitor.YAML file, instead of a monitor.INI file, was for new features.
With YAML it is much easier to extend the functionality of the application.
