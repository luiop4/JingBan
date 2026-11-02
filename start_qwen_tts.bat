@echo off
cd /d "%~dp0"
call "%~dp0prepare_portable.bat"
if errorlevel 1 (
    pause
    exit /b 1
)
set "MODELSCOPE_CACHE=%~dp0models\modelscope-cache"
set "HF_HOME=%~dp0models\huggingface-cache"
set "QWEN_PY=%~dp0.qwen-venv\Scripts\python.exe"

if not exist "%QWEN_PY%" (
    echo Run setup_qwen_tts.bat first.
    pause
    exit /b 1
)

"%QWEN_PY%" qwen_tts_server.py
pause
