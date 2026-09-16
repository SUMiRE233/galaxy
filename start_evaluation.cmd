@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo Python virtual environment not found.
  echo Run: python -m venv .venv ^&^& .venv\Scripts\pip install -r requirements-dev.txt
  pause
  exit /b 1
)

echo Starting the private Music Galaxy listening preview...
echo Labels are saved under evaluation\local_annotations and ignored by Git.
".venv\Scripts\python.exe" scripts\13_serve_human_annotation.py

if errorlevel 1 (
  echo.
  echo The preview stopped with an error.
  pause
)
endlocal
