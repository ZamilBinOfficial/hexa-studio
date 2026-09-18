#!/usr/bin/env python3
"""
Easy Video Downloader Studio - Backend Server
Author: Zamil Bin / Antigravity
Provides a local HTTP REST API for yt-dlp & FFmpeg operations.
"""

import os
import sys
import re
import json
import time
import shutil
import urllib.request
import urllib.parse
import subprocess
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn

# Ensure stdout/stderr exist when running with pythonw.exe
if sys.stdout is None:
    try:
        sys.stdout = open(os.devnull, "w")
    except Exception:
        pass
if sys.stderr is None:
    try:
        sys.stderr = open(os.devnull, "w")
    except Exception:
        pass

PORT = 5252
HOST = "127.0.0.1"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UI_DIR = os.path.join(BASE_DIR, "ui")
DOWNLOADS_DIR = os.path.join(os.path.expanduser("~"), "Downloads")
HISTORY_FILE = os.path.join(BASE_DIR, "history.json")

# Locate yt-dlp executable
def find_ytdlp():
    found = shutil.which("yt-dlp")
    if found:
        return found
    py_scripts = os.path.join(os.path.dirname(sys.executable), "Scripts", "yt-dlp.exe")
    if os.path.exists(py_scripts):
        return py_scripts
    local_prog = os.path.expandvars(r"%LOCALAPPDATA%\Programs\Python\Python312\Scripts\yt-dlp.exe")
    if os.path.exists(local_prog):
        return local_prog
    return "yt-dlp"

def find_ffmpeg():
    found = shutil.which("ffmpeg")
    if found:
        return found
    return "ffmpeg"

YTDLP_BIN = find_ytdlp()
FFMPEG_BIN = find_ffmpeg()

# Global State for active download
active_task = {
    "state": "idle",       # idle | inspecting | downloading | converting | complete | error
    "percent": 0.0,
    "speed": "0 KB/s",
    "eta": "--:--",
    "total_size": "0 MB",
    "status_text": "Ready",
    "title": "",
    "thumbnail": "",
    "url": "",
    "format": "",
    "file_path": "",
    "error_message": "",
    "process": None
}
state_lock = threading.Lock()

def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []

def save_history(entry):
    try:
        history = load_history()
        history.insert(0, entry)
        history = history[:30] # keep last 30
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Error saving history: {e}")

def get_windows_clipboard_text():
    if os.name != 'nt':
        return ""
    try:
        import ctypes
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        if not user32.OpenClipboard(None):
            return ""
        try:
            CF_UNICODETEXT = 13
            handle = user32.GetClipboardData(CF_UNICODETEXT)
            if not handle:
                return ""
            data_ptr = kernel32.GlobalLock(handle)
            if not data_ptr:
                return ""
            try:
                return ctypes.c_wchar_p(data_ptr).value or ""
            finally:
                kernel32.GlobalUnlock(handle)
        finally:
            user32.CloseClipboard()
    except Exception:
        return ""

def grab_and_save_clipboard_photo():
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    os.makedirs(DOWNLOADS_DIR, exist_ok=True)

    # 1. Direct Bitmap/Image from Windows OS clipboard (Snipping Tool, PrintScreen, Copy Image)
    try:
        from PIL import ImageGrab
        clip_data = ImageGrab.grabclipboard()
    except Exception:
        clip_data = None

    if clip_data is not None:
        if hasattr(clip_data, "save"):
            filename = f"photo_{timestamp}.png"
            filepath = os.path.join(DOWNLOADS_DIR, filename)
            try:
                if getattr(clip_data, "mode", "") in ("RGBA", "P"):
                    clip_data.save(filepath, "PNG")
                else:
                    clip_data.convert("RGB").save(filepath, "PNG")

                save_history({
                    "title": filename,
                    "thumbnail": f"/api/view-local?path={urllib.parse.quote(filepath)}",
                    "url": "Clipboard Screenshot",
                    "format": "PHOTO",
                    "file_path": filepath,
                    "file_name": filename,
                    "timestamp": int(time.time()),
                    "date_str": time.strftime("%b %d, %I:%M %p")
                })
                return {"status": "ok", "file_path": filepath, "filename": filename, "source": "clipboard_image"}
            except Exception as e:
                return {"error": f"Failed to save clipboard image: {e}"}

        elif isinstance(clip_data, list) and len(clip_data) > 0:
            for src_path in clip_data:
                if os.path.isfile(src_path):
                    ext = os.path.splitext(src_path)[1].lower()
                    if ext in [".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".ico", ".tiff", ".svg"]:
                        base = os.path.basename(src_path)
                        dest = os.path.join(DOWNLOADS_DIR, base)
                        if os.path.abspath(src_path) != os.path.abspath(dest):
                            shutil.copy2(src_path, dest)
                        else:
                            dest = src_path
                        save_history({
                            "title": base,
                            "thumbnail": f"/api/view-local?path={urllib.parse.quote(dest)}",
                            "url": "Explorer Copied Photo",
                            "format": "PHOTO",
                            "file_path": dest,
                            "file_name": base,
                            "timestamp": int(time.time()),
                            "date_str": time.strftime("%b %d, %I:%M %p")
                        })
                        return {"status": "ok", "file_path": dest, "filename": base, "source": "clipboard_file"}

    # 2. Check Clipboard text for image URL
    text = get_windows_clipboard_text().strip()
    if text and (text.startswith("http://") or text.startswith("https://")):
        try:
            req = urllib.request.Request(text, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                content_type = resp.headers.get("Content-Type", "")
                img_bytes = resp.read()
                ext = "png"
                if "jpeg" in content_type or "jpg" in content_type or ".jpg" in text.lower():
                    ext = "jpg"
                elif "webp" in content_type or ".webp" in text.lower():
                    ext = "webp"
                elif "gif" in content_type or ".gif" in text.lower():
                    ext = "gif"

                url_clean = urllib.parse.urlparse(text).path.split("/")[-1]
                url_clean = re.sub(r'[\\/*?:"<>|]', "", url_clean)
                if url_clean and len(url_clean) > 3 and "." in url_clean:
                    filename = f"photo_{url_clean}"
                else:
                    filename = f"photo_{timestamp}.{ext}"

                filepath = os.path.join(DOWNLOADS_DIR, filename)
                with open(filepath, "wb") as f:
                    f.write(img_bytes)

                save_history({
                    "title": filename,
                    "thumbnail": text,
                    "url": text,
                    "format": "PHOTO",
                    "file_path": filepath,
                    "file_name": filename,
                    "timestamp": int(time.time()),
                    "date_str": time.strftime("%b %d, %I:%M %p")
                })
                return {"status": "ok", "file_path": filepath, "filename": filename, "source": "url"}
        except Exception as e:
            return {"error": f"Failed to download image from link: {e}"}

    return {"error": "Clipboard empty! Take a screenshot (Win+Shift+S) or copy an image first."}

class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True

class StudioHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Silence routine access logs
        return

    def send_json(self, data, status=200):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == "/api/status":
            self.send_json({
                "status": "ready",
                "ytdlp_found": shutil.which(YTDLP_BIN) is not None or os.path.exists(YTDLP_BIN),
                "ytdlp_bin": YTDLP_BIN,
                "downloads_dir": DOWNLOADS_DIR,
                "ffmpeg_found": shutil.which(FFMPEG_BIN) is not None
            })
            return

        elif path == "/api/progress":
            with state_lock:
                data = {
                    "state": active_task["state"],
                    "percent": active_task["percent"],
                    "speed": active_task["speed"],
                    "eta": active_task["eta"],
                    "total_size": active_task["total_size"],
                    "status_text": active_task["status_text"],
                    "title": active_task["title"],
                    "file_path": active_task["file_path"],
                    "error_message": active_task["error_message"]
                }
            self.send_json(data)
            return

        elif path == "/api/view-local":
            q = urllib.parse.parse_qs(parsed.query)
            fp = q.get("path", [""])[0]
            if fp and os.path.exists(fp) and os.path.isfile(fp):
                try:
                    with open(fp, "rb") as f:
                        data = f.read()
                    self.send_response(200)
                    self.send_header("Content-Type", "image/png")
                    self.send_header("Content-Length", str(len(data)))
                    self.end_headers()
                    self.wfile.write(data)
                    return
                except Exception:
                    pass
            self.send_response(404)
            self.end_headers()
            return

        elif path == "/api/grab-clipboard-photo":
            result = grab_and_save_clipboard_photo()
            if "error" in result:
                self.send_json(result, 400)
            else:
                self.send_json(result, 200)
            return

        elif path == "/api/history":
            self.send_json(load_history())
            return


        # Serve static files
        if path == "/" or path == "/index.html":
            file_path = os.path.join(UI_DIR, "index.html")
            content_type = "text/html; charset=utf-8"
        elif path == "/favicon.ico":
            file_path = os.path.join(UI_DIR, "favicon.ico")
            content_type = "image/x-icon"
        else:
            rel_path = path.lstrip("/\\")
            file_path = os.path.join(UI_DIR, rel_path)
            if file_path.endswith(".css"):
                content_type = "text/css"
            elif file_path.endswith(".js"):
                content_type = "application/javascript"
            elif file_path.endswith(".svg"):
                content_type = "image/svg+xml"
            elif file_path.endswith(".png"):
                content_type = "image/png"
            elif file_path.endswith(".ico"):
                content_type = "image/x-icon"
            else:
                content_type = "text/plain"

        if os.path.exists(file_path) and os.path.isfile(file_path):
            try:
                with open(file_path, "rb") as f:
                    content = f.read()
                self.send_response(200)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(content)))
                self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
                self.end_headers()
                self.wfile.write(content)
            except Exception as e:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(str(e).encode())
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"404 Not Found")

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode("utf-8") if length > 0 else "{}"
        try:
            payload = json.loads(body)
        except Exception:
            payload = {}

        if path == "/api/info":
            url = payload.get("url", "").strip()
            if not url:
                self.send_json({"error": "No URL provided"}, 400)
                return

            def fetch_meta():
                cmd = [
                    YTDLP_BIN,
                    "--dump-single-json",
                    "--no-playlist",
                    "--no-warnings",
                    "--quiet",
                    url
                ]
                try:
                    p = subprocess.run(
                        cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        timeout=18,
                        creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
                    )
                    if p.returncode == 0 and p.stdout.strip():
                        info = json.loads(p.stdout)
                        return {
                            "title": info.get("title", "Video"),
                            "thumbnail": info.get("thumbnail") or (info.get("thumbnails")[-1]["url"] if info.get("thumbnails") else ""),
                            "duration_string": info.get("duration_string") or format_duration(info.get("duration", 0)),
                            "uploader": info.get("uploader") or info.get("channel") or "Unknown Creator",
                            "extractor": info.get("extractor_key") or "Web Video",
                            "view_count": info.get("view_count", 0),
                            "url": url
                        }
                except Exception as ex:
                    print(f"yt-dlp info error: {ex}")
                # Fallback info
                return {
                    "title": url,
                    "thumbnail": "",
                    "duration_string": "Available",
                    "uploader": "Online Video",
                    "extractor": "Web",
                    "url": url
                }

            result = fetch_meta()
            self.send_json(result)
            return

        elif path == "/api/download":
            url = payload.get("url", "").strip()
            fmt = payload.get("format", "best_mp4")
            title = payload.get("title", "Video")
            thumb = payload.get("thumbnail", "")
            trim_enabled = payload.get("trim_enabled", False)
            start_time = payload.get("start_time", "").strip()
            end_time = payload.get("end_time", "").strip()
            mute_video = payload.get("mute_video", False)

            if not url:
                self.send_json({"error": "Missing URL"}, 400)
                return

            with state_lock:
                if active_task["state"] in ["downloading", "converting"]:
                    self.send_json({"error": "A download is already in progress"}, 409)
                    return

                active_task["state"] = "downloading"
                active_task["percent"] = 0.0
                active_task["speed"] = "Connecting..."
                active_task["eta"] = "Calculating..."
                active_task["total_size"] = "Calculating..."
                active_task["status_text"] = "Initializing engine..."
                active_task["title"] = title + (" (Clip)" if trim_enabled else "")
                active_task["thumbnail"] = thumb
                active_task["url"] = url
                active_task["format"] = fmt + ("_cut" if trim_enabled else "")
                active_task["file_path"] = ""
                active_task["error_message"] = ""

            t = threading.Thread(
                target=run_download_worker,
                args=(url, fmt, title, thumb, start_time if trim_enabled else None, end_time if trim_enabled else None, mute_video)
            )
            t.daemon = True
            t.start()

            self.send_json({"status": "started"})
            return

        elif path == "/api/download-thumbnail":
            thumb_url = payload.get("thumbnail", "").strip()
            title = payload.get("title", "thumbnail").strip()
            if not thumb_url:
                self.send_json({"error": "No thumbnail URL available"}, 400)
                return
            safe_title = re.sub(r'[\\/*?:"<>|]', "", title)[:60]
            out_file = os.path.join(DOWNLOADS_DIR, f"{safe_title}_thumbnail.jpg")
            try:
                req = urllib.request.Request(thumb_url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=15) as resp, open(out_file, "wb") as f:
                    f.write(resp.read())
                save_history({
                    "title": f"Thumbnail: {title}",
                    "thumbnail": thumb_url,
                    "url": thumb_url,
                    "format": "thumb",
                    "file_path": out_file,
                    "file_name": os.path.basename(out_file),
                    "timestamp": int(time.time()),
                    "date_str": time.strftime("%b %d, %I:%M %p")
                })
                self.send_json({"status": "ok", "file_path": out_file})
            except Exception as e:
                self.send_json({"error": str(e)}, 500)
            return

        elif path == "/api/download-subtitles":
            url = payload.get("url", "").strip()
            title = payload.get("title", "Video").strip()
            if not url:
                self.send_json({"error": "Missing URL"}, 400)
                return
            try:
                cmd = [
                    YTDLP_BIN,
                    "--write-sub",
                    "--write-auto-sub",
                    "--sub-lang", "en.*",
                    "--convert-subs", "srt",
                    "--skip-download",
                    "-P", DOWNLOADS_DIR,
                    "-o", "%(title)s [%(id)s].%(ext)s",
                    url
                ]
                proc = subprocess.run(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=30,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
                )
                self.send_json({"status": "ok"})
            except Exception as e:
                self.send_json({"error": str(e)}, 500)
            return

        elif path == "/api/grab-clipboard-photo":
            result = grab_and_save_clipboard_photo()
            if "error" in result:
                self.send_json(result, 400)
            else:
                self.send_json(result, 200)
            return

        elif path == "/api/save-photo":
            img_data_b64 = payload.get("image_base64", "").strip()
            img_url = payload.get("url", "").strip()
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            os.makedirs(DOWNLOADS_DIR, exist_ok=True)

            if img_data_b64:
                if "," in img_data_b64:
                    header, b64_str = img_data_b64.split(",", 1)
                    ext = "png"
                    if "jpeg" in header or "jpg" in header:
                        ext = "jpg"
                    elif "webp" in header:
                        ext = "webp"
                else:
                    b64_str = img_data_b64
                    ext = "png"

                import base64
                try:
                    img_bytes = base64.b64decode(b64_str)
                    filename = f"photo_{timestamp}.{ext}"
                    filepath = os.path.join(DOWNLOADS_DIR, filename)
                    with open(filepath, "wb") as f:
                        f.write(img_bytes)

                    save_history({
                        "title": filename,
                        "thumbnail": f"/api/view-local?path={urllib.parse.quote(filepath)}",
                        "url": "Clipboard Image",
                        "format": "PHOTO",
                        "file_path": filepath,
                        "file_name": filename,
                        "timestamp": int(time.time()),
                        "date_str": time.strftime("%b %d, %I:%M %p")
                    })
                    self.send_json({"status": "ok", "file_path": filepath, "filename": filename})
                    return
                except Exception as e:
                    self.send_json({"error": f"Failed to save clipboard image: {e}"}, 500)
                    return

            elif img_url:
                try:
                    req = urllib.request.Request(img_url, headers={"User-Agent": "Mozilla/5.0"})
                    with urllib.request.urlopen(req, timeout=15) as resp:
                        img_bytes = resp.read()
                        content_type = resp.headers.get("Content-Type", "")
                        ext = "png"
                        if "jpeg" in content_type or "jpg" in content_type or ".jpg" in img_url.lower():
                            ext = "jpg"
                        elif "webp" in content_type or ".webp" in img_url.lower():
                            ext = "webp"
                        elif "gif" in content_type or ".gif" in img_url.lower():
                            ext = "gif"

                    url_clean = urllib.parse.urlparse(img_url).path.split("/")[-1]
                    url_clean = re.sub(r'[\\/*?:"<>|]', "", url_clean)
                    if url_clean and len(url_clean) > 3 and "." in url_clean:
                        filename = f"photo_{url_clean}"
                    else:
                        filename = f"photo_{timestamp}.{ext}"

                    filepath = os.path.join(DOWNLOADS_DIR, filename)
                    with open(filepath, "wb") as f:
                        f.write(img_bytes)

                    save_history({
                        "title": filename,
                        "thumbnail": img_url,
                        "url": img_url,
                        "format": "PHOTO",
                        "file_path": filepath,
                        "file_name": filename,
                        "timestamp": int(time.time()),
                        "date_str": time.strftime("%b %d, %I:%M %p")
                    })
                    self.send_json({"status": "ok", "file_path": filepath, "filename": filename})
                    return
                except Exception as e:
                    self.send_json({"error": f"Failed to download image: {e}"}, 500)
                    return

            else:
                self.send_json({"error": "No image data or URL provided"}, 400)
                return



        elif path == "/api/cancel":
            with state_lock:
                p = active_task.get("process")
                if p and p.poll() is None:
                    try:
                        p.terminate()
                        active_task["state"] = "error"
                        active_task["error_message"] = "Download cancelled by user."
                    except Exception as e:
                        print(f"Cancel error: {e}")
            self.send_json({"status": "cancelled"})
            return

        elif path == "/api/open-downloads":
            try:
                os.makedirs(DOWNLOADS_DIR, exist_ok=True)
                if os.name == 'nt':
                    os.startfile(DOWNLOADS_DIR)
                else:
                    subprocess.Popen(['xdg-open', DOWNLOADS_DIR])
                self.send_json({"status": "opened"})
            except Exception as e:
                self.send_json({"error": str(e)}, 500)
            return

        elif path == "/api/open-file":
            filepath = payload.get("path", "")
            if not filepath:
                with state_lock:
                    filepath = active_task.get("file_path", "")

            if filepath and os.path.exists(filepath):
                try:
                    if os.name == 'nt':
                        subprocess.Popen(f'explorer /select,"{filepath}"')
                    else:
                        subprocess.Popen(['xdg-open', filepath])
                    self.send_json({"status": "selected"})
                except Exception as e:
                    self.send_json({"error": str(e)}, 500)
            else:
                self.send_json({"error": "File not found"}, 404)
            return

        self.send_json({"error": "Endpoint not found"}, 404)

def format_duration(seconds):
    if not seconds:
        return "--:--"
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"

def run_download_worker(url, fmt, title, thumb, trim_start=None, trim_end=None, mute=False):
    # Output template matches user's preferred naming
    is_clipped = bool(trim_start and trim_end)
    out_name = "%(title)s [%(id)s]_clip.%(ext)s" if is_clipped else "%(title)s [%(id)s].%(ext)s"

    cmd = [
        YTDLP_BIN,
        "--newline",
        "--no-mtime",
        "-P", DOWNLOADS_DIR,
        "-o", out_name
    ]

    if is_clipped:
        cmd.extend(["--download-sections", f"*{trim_start}-{trim_end}", "--force-keyframes-at-cuts"])

    if mute and fmt in ["best_mp4", "1080p", "4k"]:
        # Mute video (video stream only, no audio)
        if fmt == "1080p":
            cmd.extend(["-f", "bv*[height<=1080][ext=mp4]/b[height<=1080]", "--merge-output-format", "mp4"])
        elif fmt == "4k":
            cmd.extend(["-f", "bv*[height<=2160][ext=mp4]/b[height<=2160]", "--merge-output-format", "mp4"])
        else:
            cmd.extend(["-f", "bv*[ext=mp4]/b[ext=mp4]/best", "--merge-output-format", "mp4"])
    else:
        if fmt == "best_mp4":
            # 1: Best Quality MP4 Video (Recommended for Premiere Pro)
            cmd.extend(["-f", "bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/best", "--merge-output-format", "mp4"])
        elif fmt == "1080p":
            # 2: 1080p MP4 Video
            cmd.extend(["-f", "bv*[height<=1080][ext=mp4]+ba[ext=m4a]/b[height<=1080]", "--merge-output-format", "mp4"])
        elif fmt == "4k":
            # 3: 4K MP4 Video
            cmd.extend(["-f", "bv*[height<=2160][ext=mp4]+ba[ext=m4a]/b[height<=2160]", "--merge-output-format", "mp4"])
        elif fmt == "mp3":
            # 4: Audio Only (MP3 320k)
            cmd.extend(["-x", "--audio-format", "mp3", "--audio-quality", "0"])
        elif fmt == "wav":
            # 5: Audio Only (Lossless WAV for Premiere Pro)
            cmd.extend(["-x", "--audio-format", "wav"])
        elif fmt == "playlist":
            # 6: Download Full Playlist (MP4)
            cmd.extend(["-f", "bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/best", "--yes-playlist", "--merge-output-format", "mp4"])
        else:
            cmd.extend(["-f", "bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/best", "--merge-output-format", "mp4"])

    cmd.append(url)


    re_prog = re.compile(r'\[download\]\s+(\d+\.?\d*)%\s+of\s+~?([0-9\.]+[A-Za-z]+)\s+at\s+([0-9\.]+[A-Za-z/]+)\s+ETA\s+(\S+)')
    re_merging = re.compile(r'\[Merger\]|\[ExtractAudio\]|\[ffmpeg\]')
    re_dest = re.compile(r'\[(?:download|Merger|ExtractAudio)\] Destination:\s*(.+)')
    re_already = re.compile(r'\[download\]\s*(.+?)\s*has already been downloaded')

    downloaded_filepath = ""

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        )
        with state_lock:
            active_task["process"] = proc

        for raw_line in proc.stdout:
            line = raw_line.strip()
            if not line:
                continue

            # Check destination
            m_dest = re_dest.search(line)
            if m_dest:
                candidate = m_dest.group(1).strip()
                if not os.path.isabs(candidate):
                    candidate = os.path.join(DOWNLOADS_DIR, candidate)
                downloaded_filepath = candidate

            m_already = re_already.search(line)
            if m_already:
                candidate = m_already.group(1).strip()
                if not os.path.isabs(candidate):
                    candidate = os.path.join(DOWNLOADS_DIR, candidate)
                downloaded_filepath = candidate

            # Check progress
            m = re_prog.search(line)
            if m:
                percent = float(m.group(1))
                size = m.group(2)
                speed = m.group(3)
                eta = m.group(4)

                with state_lock:
                    active_task["percent"] = percent
                    active_task["total_size"] = size
                    active_task["speed"] = speed
                    active_task["eta"] = eta
                    active_task["status_text"] = f"Downloading streams... {percent:.1f}%"

            elif re_merging.search(line):
                with state_lock:
                    active_task["percent"] = 99.0
                    active_task["status_text"] = "Merging audio/video with FFmpeg..."
                    active_task["speed"] = "Processing"
                    active_task["eta"] = "Almost done"

        proc.wait()

        if proc.returncode == 0:
            # If downloaded file path is not identified, search for newest file in Downloads
            if not downloaded_filepath or not os.path.exists(downloaded_filepath):
                try:
                    files = [os.path.join(DOWNLOADS_DIR, f) for f in os.listdir(DOWNLOADS_DIR)]
                    files = [f for f in files if os.path.isfile(f)]
                    if files:
                        downloaded_filepath = max(files, key=os.path.getmtime)
                except Exception:
                    pass

            with state_lock:
                active_task["state"] = "complete"
                active_task["percent"] = 100.0
                active_task["status_text"] = "Download Complete!"
                active_task["file_path"] = downloaded_filepath

            # Add to history
            save_history({
                "title": title or os.path.basename(downloaded_filepath),
                "thumbnail": thumb,
                "url": url,
                "format": fmt,
                "file_path": downloaded_filepath,
                "file_name": os.path.basename(downloaded_filepath) if downloaded_filepath else "Media",
                "timestamp": int(time.time()),
                "date_str": time.strftime("%b %d, %I:%M %p")
            })

        else:
            with state_lock:
                if active_task["state"] != "error":
                    active_task["state"] = "error"
                    active_task["error_message"] = "Download failed. Please verify the URL or format availability."

    except Exception as e:
        with state_lock:
            active_task["state"] = "error"
            active_task["error_message"] = str(e)
    finally:
        with state_lock:
            active_task["process"] = None

def main():
    os.makedirs(UI_DIR, exist_ok=True)
    os.makedirs(DOWNLOADS_DIR, exist_ok=True)

    server = ThreadedHTTPServer((HOST, PORT), StudioHandler)
    print(f"[*] Easy Video Downloader Studio Server running at http://{HOST}:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server.")
        server.server_close()

if __name__ == "__main__":
    main()
