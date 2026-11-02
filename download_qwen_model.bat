@echo off
setlocal
cd /d "%~dp0"
if not exist ".qwen-venv\Scripts\python.exe" (
    echo Please run setup_qwen_tts.bat first.
    pause
    exit /b 1
)
set "MODELSCOPE_CACHE=%~dp0models\modelscope-cache"
"%~dp0.qwen-venv\Scripts\python.exe" download_qwen_model.py
if errorlevel 1 (
    echo Model download did not finish. You can run this file again to resume.
    pause
    exit /b 1
)
echo The model is ready in the project models folder.
pause
