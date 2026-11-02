@echo off
setlocal
cd /d "%~dp0"

set "UV_PYTHON_INSTALL_DIR=%~dp0runtime\python"
set "UV_PYTHON_NO_REGISTRY=1"
set "UV_CACHE_DIR=%~dp0runtime\uv-cache"
set "UV=%~dp0tools\uv.exe"

if not exist "%UV%" (
    echo Missing tools\uv.exe. Copy the complete project folder before setup.
    goto failed
)

"%UV%" python install 3.12.15 --no-registry --no-bin
if errorlevel 1 goto failed

if exist ".app-venv\Scripts\python.exe" rmdir /s /q ".app-venv"
if exist ".app-venv" rmdir /s /q ".app-venv"
"%UV%" venv --python 3.12.15 --managed-python ".app-venv"
if errorlevel 1 goto failed

set "APP_PY=%~dp0.app-venv\Scripts\python.exe"
if exist "requirements-app.lock.txt" goto install_locked

"%UV%" pip install --python "%APP_PY%" -r requirements.txt
if errorlevel 1 goto failed
goto save_lock

:install_locked
"%UV%" pip install --python "%APP_PY%" -r requirements-app.lock.txt
if errorlevel 1 goto failed

:save_lock
"%UV%" pip freeze --python "%APP_PY%" > requirements-app.lock.txt
if errorlevel 1 goto failed
echo Chat application environment is ready. Start the app with start.bat.
pause
exit /b 0

:failed
echo Setup did not finish. Read the message above and run this file again.
pause
exit /b 1
