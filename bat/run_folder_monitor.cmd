@echo off
@REM Run this script in folder bat
python ../scripts/folder_monitor.py --destination-path "e2:test-zoetebier-net/Test" --monitor-path "D:\Test\FolderMonitor" --base-path "Test" --sync-mode "True" --monitor-config-path "../conf/monitor.yaml"
@REM python ../scripts/folder_monitor.py --destination-path "e2:john-zoetebier-net/Cloud" --monitor-path "D:\Cloud" --base-path "Cloud" --sync-mode "True" --monitor-config-path "../conf/monitor.yaml"
@REM python ../scripts/folder_monitor.py --destination-path "e2:test-zoetebier-net/Test2" --monitor-path "D:\Test2\FolderMonitor" --base-path "Test2" --sync-mode "True" --monitor-config-path "../conf/monitor.yaml"
