@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
set "PYTHONHOME="
set "PYTHONPATH="
for %%F in (launcher.py ui_launcher.py portable_runtime.py update_core.py update_trust.py startup_support.py prepare_portable.bat) do if not exist "%~dp0%%F" goto rescue
call "%~dp0prepare_portable.bat"
if errorlevel 1 goto rescue
"%~dp0.app-venv\Scripts\python.exe" "%~dp0launcher.py"
if errorlevel 1 goto rescue
endlocal
exit /b 0
:rescue
if not exist "%~dp0鲸伴.exe" goto failed
"%~dp0鲸伴.exe"
if errorlevel 1 goto failed
endlocal
exit /b 0
:failed
echo Application could not start. See the details above.
pause
endlocal
exit /b 1
