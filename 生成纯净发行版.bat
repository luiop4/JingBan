@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
set "PYTHONHOME="
set "PYTHONPATH="
set "RELEASE_PY=%~dp0runtime\python\cpython-3.12.15-windows-x86_64-none\python.exe"
if not exist "%RELEASE_PY%" goto missing_python
"%RELEASE_PY%" -X utf8 "%~dp0build_clean_release.py" %*
if errorlevel 1 goto failed
echo.
echo 已生成可分发的纯净目录。默认位于项目旁边的“鲸伴发行”文件夹。
echo 请分发新生成的目录，接收者首次启动后填写自己的 API 设置。
pause
exit /b 0
:missing_python
echo 缺少项目内 Python，请先恢复 runtime 文件夹。
:failed
echo 生成失败，请查看上面的原因。不要分发未完成的目录。
pause
exit /b 1
