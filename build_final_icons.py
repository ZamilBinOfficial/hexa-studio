import os
import subprocess
from PIL import Image

base_dir = r"Z:\Hub\projects\easy-downloader"
cropped_path = r"C:\Users\xorbi\.gemini\antigravity\brain\f58ae0a6-db9c-461c-b7c7-1a0f9dae4221\cropped_original.png"
desktop = os.path.join(os.path.expanduser("~"), "Desktop")

img = Image.open(cropped_path).convert("RGBA")

# Ensure it is a clean 512x512 square
final_512 = img.resize((512, 512), Image.Resampling.LANCZOS)

ui_icon = os.path.join(base_dir, "ui", "icon.png")
ui_favicon = os.path.join(base_dir, "ui", "favicon.ico")
hexa_ico = os.path.join(base_dir, "hexa_icon.ico")

final_512.save(ui_icon, "PNG")

sizes = [(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)]
final_512.save(ui_favicon, format="ICO", sizes=sizes)
final_512.save(hexa_ico, format="ICO", sizes=sizes)

print("Icons saved to:", ui_icon, ui_favicon, hexa_ico)

# Create/Update Desktop Shortcut
old_lnk = os.path.join(desktop, "Easy Video Downloader.lnk")
if os.path.exists(old_lnk):
    try:
        os.remove(old_lnk)
    except Exception:
        pass

new_lnk = os.path.join(desktop, "HEXA Studio.lnk")
target_bat = r"C:\Users\xorbi\Desktop\Easy_Video_Downloader.bat"

ps_code = f"""
$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut("{new_lnk}")
$Shortcut.TargetPath = "{target_bat}"
$Shortcut.WorkingDirectory = "{base_dir}"
$Shortcut.IconLocation = "{hexa_ico},0"
$Shortcut.Save()
"""

subprocess.run(["powershell", "-NoProfile", "-Command", ps_code], check=True)
print(f"Created/Updated Desktop Shortcut: {new_lnk}")
