import os
import subprocess

desktop = os.path.join(os.path.expanduser("~"), "Desktop")
shortcut_path = os.path.join(desktop, "Easy Video Downloader.lnk")
target_bat = r"C:\Users\xorbi\Desktop\Easy_Video_Downloader.bat"
icon_path = r"Z:\Hub\projects\easy-downloader\icon.ico"
work_dir = r"Z:\Hub\projects\easy-downloader"

ps_code = f"""
$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut("{shortcut_path}")
$Shortcut.TargetPath = "{target_bat}"
$Shortcut.WorkingDirectory = "{work_dir}"
$Shortcut.IconLocation = "{icon_path},0"
$Shortcut.Save()
"""

subprocess.run(["powershell", "-NoProfile", "-Command", ps_code], check=True)
print("Shortcut created successfully at:", shortcut_path)
