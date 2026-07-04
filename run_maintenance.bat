@echo off
cd /d "C:\Users\user\OneDrive\Desktop\projects\second-brain v1"
".venv\Scripts\python.exe" -m src.workflows.maintenance --apply-safe-fixes >> "maintenance.log" 2>&1
