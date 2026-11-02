@echo off
setlocal
cd /d "%~dp0"
call "%~dp0prepare_portable.bat"
if errorlevel 1 goto failed

set "APP_PY=%~dp0.app-venv\Scripts\python.exe"
set "PYINSTALLER=%~dp0.app-venv\Scripts\pyinstaller.exe"
set "UV=%~dp0tools\uv.exe"

if not exist "%APP_PY%" (
    echo Please run setup_app.bat first.
    pause
    exit /b 1
)

if not exist "%PYINSTALLER%" (
    if not exist "%UV%" (
        echo Missing tools\uv.exe. Cannot prepare the launcher packager.
        pause
        exit /b 1
    )
    echo Preparing the launcher packager in .app-venv...
    "%UV%" pip install --python "%APP_PY%" pyinstaller
    if errorlevel 1 goto failed
)

"%APP_PY%" -m PyInstaller -y --clean --distpath "%~dp0." --workpath "%TEMP%\AIChatMemoryLauncher-build" "%~dp0AIChatMemoryLauncher.spec"
if errorlevel 1 goto failed

echo Launcher created. See the project folder.
echo Keep it beside main.py and .app-venv. The application files and data are not bundled.
pause
exit /b 0

:failed
echo Launcher packaging did not finish. Read the message above and try again.
pause
exit /b 1
