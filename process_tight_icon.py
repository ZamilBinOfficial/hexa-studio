import os
import subprocess
from PIL import Image

base_dir = r"Z:\Hub\projects\easy-downloader"
raw_path = os.path.join(base_dir, "raw_icon.jpg")
desktop = os.path.join(os.path.expanduser("~"), "Desktop")

img = Image.open(raw_path).convert("RGBA")

# Bounding box of the white glyph: (165, 177, 399, 387)
# Center: ((165+399)/2, (177+387)/2) = (282, 282)
# Width: 234, Height: 210
# Max dimension = 234
glyph = img.crop((165, 177, 399, 387))

# Make background of cropped glyph transparent
datas = list(glyph.getdata())
clean_data = []
for item in datas:
    # If dark, transparent
    if item[0] < 30 and item[1] < 30 and item[2] < 30:
        clean_data.append((0, 0, 0, 0))
    else:
        # Boost brightness/clarity to pure clean white/silver
        clean_data.append((255, 255, 255, item[3]))

glyph.putdata(clean_data)

# Create a 512x512 canvas and center the glyph so it fills ~80% of the canvas
canvas_size = 512
glyph_target_size = 400
# Maintain aspect ratio
ratio = glyph_target_size / max(glyph.size)
new_w = int(glyph.size[0] * ratio)
new_h = int(glyph.size[1] * ratio)
glyph_resized = glyph.resize((new_w, new_h), Image.Resampling.LANCZOS)

final_img = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
offset_x = (canvas_size - new_w) // 2
offset_y = (canvas_size - new_h) // 2
final_img.paste(glyph_resized, (offset_x, offset_y), glyph_resized)

# Save web icon & favicons
ui_icon_png = os.path.join(base_dir, "ui", "icon.png")
ui_favicon_ico = os.path.join(base_dir, "ui", "favicon.ico")
hexa_ico = os.path.join(base_dir, "hexa_icon.ico")
brain_preview = r"C:\Users\xorbi\.gemini\antigravity\brain\f58ae0a6-db9c-461c-b7c7-1a0f9dae4221\hexa_preview.png"

final_img.save(ui_icon_png, "PNG")
final_img.save(brain_preview, "PNG")

sizes = [(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)]
final_img.save(ui_favicon_ico, format="ICO", sizes=sizes)
final_img.save(hexa_ico, format="ICO", sizes=sizes)

print("Icons saved successfully!")

# Remove old desktop shortcut if exists
old_lnk = os.path.join(desktop, "Easy Video Downloader.lnk")
if os.path.exists(old_lnk):
    try:
        os.remove(old_lnk)
    except Exception:
        pass

# Create new branded shortcut: HEXA Studio.lnk
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
print(f"Created new branded shortcut: {new_lnk}")
