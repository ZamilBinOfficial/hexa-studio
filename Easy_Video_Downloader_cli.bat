@echo off
title Quick Video & Audio Downloader (CLI Legacy)
color 0A

:menu
cls
echo =======================================================
echo          QUICK VIDEO & AUDIO DOWNLOADER (yt-dlp)
echo =======================================================
echo.
echo Downloads will be saved to your "Downloads" folder.
echo.
set /p "url=Paste Video URL: "
if "%url%"=="" goto menu

echo.
echo Choose Download Option:
echo [1] Best Quality MP4 Video (Recommended for Premiere Pro)
echo [2] 1080p MP4 Video
echo [3] 4K MP4 Video
echo [4] Audio Only (MP3)
echo [5] Audio Only (Lossless WAV for Premiere Pro)
echo [6] Download Full Playlist (MP4)
echo.
set /p "choice=Enter choice [1-6]: "

echo.
echo =======================================================
echo Downloading... please wait.
echo =======================================================
echo.

if "%choice%"=="1" (
    yt-dlp -P "%USERPROFILE%\Downloads" -f "bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/best" --merge-output-format mp4 "%url%"
) else if "%choice%"=="2" (
    yt-dlp -P "%USERPROFILE%\Downloads" -f "bv*[height<=1080][ext=mp4]+ba[ext=m4a]/b[height<=1080]" --merge-output-format mp4 "%url%"
) else if "%choice%"=="3" (
    yt-dlp -P "%USERPROFILE%\Downloads" -f "bv*[height<=2160][ext=mp4]+ba[ext=m4a]/b[height<=2160]" --merge-output-format mp4 "%url%"
) else if "%choice%"=="4" (
    yt-dlp -P "%USERPROFILE%\Downloads" -x --audio-format mp3 --audio-quality 0 "%url%"
) else if "%choice%"=="5" (
    yt-dlp -P "%USERPROFILE%\Downloads" -x --audio-format wav "%url%"
) else if "%choice%"=="6" (
    yt-dlp -P "%USERPROFILE%\Downloads" -f "bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/best" --yes-playlist --merge-output-format mp4 "%url%"
) else (
    echo Invalid choice.
)

echo.
echo =======================================================
echo Download finished! Saved to your Downloads folder.
echo =======================================================
echo.
pause
goto menu
