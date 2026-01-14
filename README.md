<img src="https://aip.transparent.co.nz/wp-content/uploads/2025/06/AIP_grey_transparent_background_github-e1750625832556.png" alt="AIP logo">

[Website](https://aip.transparent.co.nz) |
[Documentation](https://aip.transparent.co.nz/foldermonitor/) |


# 🚀 Quick Start

1. **Install Python**: Download from [rclone.org](https://rclone.org/) and add it to your PATH.
2. **Install rclone**: Download from [python.org](https://www.python.org/downloads/) and add it to your PATH.
3. **Recommended: Setup Python Environment**:
  
    ```bash
    # Create a virtual environment if needed, for example in your application folder
    python -m venv .venv
    
    # Activate the environment
    # On Windows:
    .\.venv\Scripts\activate

    # On macOS/Linux:
    source .venv/bin/activate
    ```

4. **Install Requirements**:

    ```bash
    pip install -r requirements.txt
    ```


4. **Verify: Run the self-test script**:

    ```bash
    python check-env.py
    ```

6. **Verify: Validate your config.yaml file**:

    ```bash
    python config_models.py
    ```

7. **Run FolderMonitor**:    
   python folder_monitor.py --config-path "./conf/config.yaml"


# FolderMonitor
FolderMonitor monitors a folder for changes and propagest thos changes to a target destination.  
The target destination is usually a cloud storage provider like iDrive, BackBlaze, Amazon S3 or Google Drive.  
Examples of other targets are a shared drive, a local drive or an FTP share.  
FolderMonitor uses rclone as a tool to propagate changes.

## Acknowledgments
This project was developed with the assistance of Google Gemini.  

## Features

  * folder_monitor.py  
    This is the core script that monitors a folder for changes and propagates changes to the destination.  
    Call example:  
      python folder_monitor.py --config-path "./conf/config.yaml 
  * YAML configuration file
    The YAML configuration file, default ./conf/config.yaml, contains settings for logging and one or more monitors

## Installation & documentation
| Application or module | How to install |
|---|---|
| rclone | Download from https://rclone.org/downloads/ |
| Python | Download from https://rclone.org/downloads/ |
| FolderMonitor | Download ZIP file from GitHub or git clone the repository  |
| watchog | Use pip installer. See below |
| PyYAML | Use pip installer. See below |

Notes:  
Best practice is to download and install rclone and Python from their official download locations.
If you install from the Windows store or using Winget you may not get all components.

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
You can find more information on website: https://aip.transparent.co.nz

Project FolderMonitor grew organically over time.
All tools I used had some problem, like no real backup, cloud provider locking, hard to debug, huge CPU usage (let me guess ...)
Initially I used OneDrive to "backup" files to the OneDrive cloud storage.  
However with several file explorers running simulteneously the PC became unresponsive.  
OneDrive was frequently using 100% CPU making working on the PC impossible.
This was a deal breaker to me, I uninstalled OneDrive and decided to use rclone for copying files to the cloud.  

Rclone worked better than OneDrive and unobtrusive in the background.  
I scheduled an rclone job every few hours and this was just fine for my purposes.  
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
Future development depends on community support and request coming from the community.

Some new features could include:
- Intrusion detection and ransomware protection
  Monitoring changes of files and folders could trigger an alarm, like email, SMS message or a Discours event.
- Trigger a CI/CD job
- Develop a GUI to configure and start a monitor

---
### 👤 Author
**John Zoetebier**
- Website: [aip.transparent.co.nz](http://aip.transparent.co.nz)
- GitHub: [@yourusername]