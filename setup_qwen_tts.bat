@echo off
setlocal
cd /d "%~dp0"

set "APP_PY=%~dp0.app-venv\Scripts\python.exe"
if not exist "%APP_PY%" (
    echo The app environment is missing. Run setup_app.bat first.
    goto failed
)

"%APP_PY%" prepare_local_tts.py
if errorlevel 1 goto failed

echo Local Qwen TTS is ready.
if /I not "%~1"=="--no-pause" pause
exit /b 0

:failed
echo Local TTS setup did not finish. Read the message above and run this file again.
if /I not "%~1"=="--no-pause" pause
exit /b 1
