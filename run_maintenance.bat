@echo off
cd /d "%~dp0"
".venv\Scripts\python.exe" -m src.workflows.maintenance --apply-safe-fixes >> "maintenance.log" 2>&1
