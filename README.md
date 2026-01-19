# Folder Monitor

![AIP logo](https://aip.transparent.co.nz/wp-content/uploads/2025/06/AIP_grey_transparent_background_github-e1750625832556.png)

# 🚀 Quick Start

1. **Install Python**: Download from [rclone.org](https://rclone.org/downloads/) and add it to your PATH.
2. **Install rclone**: Download from [python.org](https://www.python.org/downloads/) and add it to your PATH.
3. **Setup Python Virtual Environment**:
  
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

5. **Verify: Run the self-test script**:

    ```bash
    python check-env.py
    ```

6. **Verify: Validate your config.yaml file**:

    ```bash
    python config_models.py
    ```

7. **Run FolderMonitor**:

   ```bash
   python folder_monitor.py --config-path "./conf/config.yaml"
   ```

##

# Folder Monitor

[Website](https://aip.transparent.co.nz) |
[Documentation](https://aip.transparent.co.nz/foldermonitor/) |

FolderMonitor monitors a folder and files in it for changes and propagates folders and files a target destination.  
The target destination can be a cloud storage provider, FTP server, local drive or shared folder.
Examples of cloud storage providers are:
* Microsoft OneDrive
* Google Drive
* Amazon S3
* IDrive E3
* Backblaze B2
* Any S3 compatible cloud storage provider.
* A WEBDAV server
* Any FTP server

FolderMonitor uses rclone as ActionHandler to propagate changes.
Other ActionHandlers can be added if required, for example an API ActionHandler.

## Acknowledgments

This project was developed with the assistance of Google Gemini.
There is a VS Code extension for Google Gemini Code Assist in agent mode.
Highly recommended.

## Features

* folder_monitor.py  
    This is the core script that monitors a folder for changes and propagates changes to the destination.  
    Call example:  
    python folder_monitor.py --config-path "./conf/config.yaml
* YAML configuration file
    The YAML configuration file, default ./conf/config.yaml, contains settings for logging and one or more monitors
* Decoupled architecture where file system events are decoupled from the processing of events
* Events are processed by an ActionHandler, currently RcloneActionHandler, that runs in a separate thread

## License

This is free software under the terms of the MIT license included in this package.  
See file: LICENSE

## Why FolderMonitor

You can find more information on website [aip.transparent.co.nz](https://aip.transparent.co.nz)

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
I added Google Gemini Code Assist extension. Gemini worked just great.  

## Future development

It is difficult to predict the future and what it measn for FolderMonitor.
Future development depends on community support and request.

Some new features could include:

* Intrusion detection
  This could trigger an alarm, like email, SMS message or a Discours event.
* Ransomware protection
  This could trigger an alarm, like email, SMS message or a Discours event.
* Develop a GUI to create a configuration file, test a configuration and start a monitor

---

### 👤 Author

John Zoetebier

* Website: [aip.transparent.co.nz](http://aip.transparent.co.nz)
