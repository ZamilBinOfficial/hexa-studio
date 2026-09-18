import os
import subprocess
from PIL import Image

base_dir = r"Z:\Hub\projects\easy-downloader"
raw_path = os.path.join(base_dir, "raw_icon.jpg")
desktop = os.path.join(os.path.expanduser("~"), "Desktop")
shortcut_path = os.path.join(desktop, "Easy Video Downloader.lnk")

img = Image.open(raw_path).convert("RGBA")

# Create a clean transparent background version where the dark background is transparent
# The background is pure black (0,0,0) or near black (< 20)
datas = img.getdata()
new_data = []
for item in datas:
    # item is (r, g, b, a)
    # Check if pixel is dark background
    if item[0] < 25 and item[1] < 25 and item[2] < 25:
        new_data.append((0, 0, 0, 0)) # transparent
    else:
        new_data.append(item)

transparent_img = Image.new("RGBA", img.size)
transparent_img.putdata(new_data)

# Save the transparent icon as app_icon_v3.ico
ico_path = os.path.join(base_dir, "app_icon_v3.ico")
sizes = [(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)]
transparent_img.resize((256, 256), Image.Resampling.LANCZOS).save(
    ico_path,
    format="ICO",
    sizes=sizes
)

# Also update the web app icon
png_path = os.path.join(base_dir, "ui", "icon.png")
transparent_img.save(png_path, "PNG")

# Update the desktop shortcut to point to app_icon_v3.ico (new filename busts Windows cache!)
ps_code = f"""
$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut("{shortcut_path}")
$Shortcut.TargetPath = "C:\\Users\\xorbi\\Desktop\\Easy_Video_Downloader.bat"
$Shortcut.WorkingDirectory = "{base_dir}"
$Shortcut.IconLocation = "{ico_path},0"
$Shortcut.Save()
"""

subprocess.run(["powershell", "-NoProfile", "-Command", ps_code], check=True)

# Force Windows Explorer to refresh icon cache
try:
    subprocess.run(["ie4uinit.exe", "-show"], timeout=3)
except Exception:
    pass

print("SUCCESS: Updated shortcut to app_icon_v3.ico")
