# Folder Monitor

![AIP logo](https://aip.transparent.co.nz/wp-content/uploads/2025/06/AIP_grey_transparent_background_github-e1750625832556.png)

## 🚀 Quick Start

1. **Run FolderMonitor**:

    *Option A: Using the Executable (Windows)*
    Download foldermonitor.exe from GitHub. You can find the exe file under Releases.

    ```cmd
    foldermonitor.exe -c "./conf/config.yaml"
    ```

    *Option B: Running from Source*
    
    a. **Install Python**: Download from [python.org](https://www.python.org/downloads/).
    
    b. **Setup Environment**:
    ```bash
    python -m venv .venv
    # Windows:
    ./.venv/Scripts/activate
    # macOS/Linux:
    source .venv/bin/activate
    
    pip install -r requirements.txt
    ```

    c. **Run**:
    ```bash
    python folder_monitor.py -c "./conf/config.yaml"
    ```

2 **Setup remote profiles**
  Create a new remote profile with command:
  ```bash
  foldermonitor.exe profile create  
  OR
  python folder_monitor.py profile create
  ```
  Alternatively, if you have already Rclone installed, you can import profiles with command:
    foldermonitor.exe profile import
    OR
    python folder_monitor.py profile import

  
3 **Configure monitors in config.yaml**

  When running folder monitor for the first time it will automatically generate a configuration file in config/config.yaml.
  Edit file config.yaml to add monitors.


4 **Run FolderMonitor in test mode**   
   Running folder monitor in test mode ensures your environment and config file are good.
   
   Test mode will check monitor path and if destination path is writable.
    ```bash
    foldermonitor.exe -t -c "./conf/config.yaml"
    ```
    OR
    ```bash
    python folder_monitor.py -t -c "./conf/config.yaml"
   ```


## Folder Monitor

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

S3-compatible providers represent the vast majority of the object storage market.

### S3Handler

The S3Handler is builtin to FolderMonitor.
It handles S3 compatible cloud storage providers, like:
- Amazon S3 (tested)
- Cloudflare R2 (tested)
- Idrive E2 (tested)
- Backblaze B2 (tested)
- Oracle Cloud Object Storage  
- IBM Cloud Object Storage
- Alibaba Cloud OSS
  
The S3Handler is a builtin file handler. It eliminates the need for Rclone when using S3 compatible cloud storage.  
This makes it much easier to use FolderMonitor without having to depend on Rclone.  
For small files the S3Handler is between 2 - 3 times as fast as rclone.  
For files of about 1Mb the data transfer is a fraction faster.  
FolderMonitor will use S3Handler if the remote profile is in foldermonitor.conf  
You can import the rclone S3 profiles with command:  
python folder_monitor.py profile import

Any remote profile not in foldermonitor.conf will use Rclone.

Over time we will add native handlers for common cloud storage providers and other storage types.  
This will reduce dependency on Rclone, and simplifies deployment and configuration. 

### Rclone

Rclone is the swiss knife of copying file to and from cloud storage.
Any remote profile not in foldermonitor.conf will use Rclone.


## Acknowledgments

This project was developed with the assistance of Google Gemini.
We used Gemini Code Assist in VS Code for development.
The code suggestions and quality are excellent.

## Features

* folder_monitor.py  
    This is the core script that monitors a folder for changes and propagates changes to the destination.  
    Call example:  
    python folder_monitor.py --config "./conf/config.yaml
* YAML configuration file
    The YAML configuration file, default ./conf/config.yaml, contains settings for logging and one or more monitors
* Decoupled architecture where file system events are decoupled from the processing of events
* Events are processed by an ActionHandler, currently RcloneActionHandler, that runs in a separate thread

## License

This is free software under the terms of the MIT license included in this package.  
See file: LICENSE

## Why FolderMonitor

You can find more information on website [aip.transparent.co.nz/FolderMonitor](https://aip.transparent.co.nz/FolderMonitor)

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
The logging was cumersome as well and I needed to run a separate cleanup job for the log files generated.  
The main issue was that PowerShell was running on Windows only.  

Now I had the choice to build a separate application for Linux, or build a generic solution for Windows, Linux and Mac OS.  
This is when FolderMonitor was born.  
While I had little experience with Python, it has proven to be a great choice.  
VS Code has fantastic support for Python development like code completion and debugging.  
I added the Gemini Code Assist extension. Gemini worked just great.  

## Future development

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
