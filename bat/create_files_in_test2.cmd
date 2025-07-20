@echo off
@REM echo "This is a test to trigger a monitor" > D:\Development\FolderMonitor\data\Source\Cloud\Test2/test1.txt
@REM echo "This is a test to trigger a monitor" > D:\Development\FolderMonitor\data\Source\Cloud\Test2/test2.txt
@REM mkdir -p "D:\Development\FolderMonitor\data\Source\Cloud\Test2/Subfolder"
@REM echo "This is a test to trigger a monitor" > D:\Development\FolderMonitor\data\Source\Cloud\Test2/Subfolder/test1.txt
@REM echo "This is a test to trigger a monitor" > D:\Development\FolderMonitor\data\Source\Cloud\Test2/Subfolder/test2.txt

cp -r .\data\Source\Cloud\Test2\ .\data\Destination\Cloud\Test2
