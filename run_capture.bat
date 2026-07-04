@echo off
cd /d "%~dp0"
echo [%date% %time%] Starting capture run >> capture.log
".venv\Scripts\python.exe" capture.py >> capture.log 2>&1
echo [%date% %time%] Finished capture run >> capture.log
