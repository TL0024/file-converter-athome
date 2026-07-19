@echo off
setlocal
cd /d "%~dp0"
python -c "import flask, PIL, fitz, docx, imageio_ffmpeg" >nul 2>&1
if errorlevel 1 (
  echo Installing FileConverter dependencies...
  python -m pip install -r requirements.txt
  if errorlevel 1 (
    echo.
    echo Dependency installation failed. Check the message above and try again.
    pause
    exit /b 1
  )
)
python app.py

