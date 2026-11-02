@echo off
setlocal
set "PYTHONHOME="
set "PYTHONPATH="
set "BASE_PY=%~dp0runtime\python\cpython-3.12.15-windows-x86_64-none\python.exe"
if not exist "%BASE_PY%" (
    echo Missing bundled Python. Copy the complete runtime folder.
    endlocal
    exit /b 1
)
"%BASE_PY%" -I "%~dp0portable_runtime.py"
set "PORTABLE_EXIT=%ERRORLEVEL%"
endlocal & exit /b %PORTABLE_EXIT%
