@echo on
@REM echo "This is a test to trigger a monitor" > D:\Development\FolderMonitor\data\Source\Cloud\Test1/test1.txt
@REM echo "This is a test to trigger a monitor" > D:\Development\FolderMonitor\data\Source\Cloud\Test1/test2.txt
@REM mkdir -p "D:\Development\FolderMonitor\data\Source\Cloud\Test1/Subfolder"
@REM echo "This is a test to trigger a monitor" > D:\Development\FolderMonitor\data\Source\Cloud\Test1/Subfolder/test1.txt
@REM echo "This is a test to trigger a monitor" > D:\Development\FolderMonitor\data\Source\Cloud\Test1/Subfolder/test2.txt

cp -r .\data\Source\Cloud\Test1\ .\data\Destination\Cloud\Test1
