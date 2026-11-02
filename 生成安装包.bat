@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
set "PYTHONHOME="
set "PYTHONPATH="
set "INSTALLER_PY=%~dp0runtime\python\cpython-3.12.15-windows-x86_64-none\python.exe"
if not exist "%INSTALLER_PY%" goto missing_python
echo 自动读取 version.json，生成当前版本的完整纯净安装包。
echo 同版本重复生成会另存新文件，原安装包会保留。
echo.
"%INSTALLER_PY%" -X utf8 "%~dp0build_installer.py" %*
if errorlevel 1 goto failed
echo.
echo 已生成独立安装包，默认位于项目旁边的“鲸伴发行”文件夹。
echo 把新生成的“安装包.exe”发给用户即可。
pause
exit /b 0
:missing_python
echo 缺少项目内 Python，请先恢复 runtime 文件夹。
:failed
echo 生成失败，请查看原因，不要分发未完成的文件。
pause
exit /b 1
