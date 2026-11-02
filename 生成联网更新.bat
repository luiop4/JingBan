@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
set "PYTHONHOME="
set "PYTHONPATH="
set "UPDATE_ARCHIVE=%~dp0..\鲸伴更新"
if not exist "%UPDATE_ARCHIVE%\签名密钥\release-signing-key.xml" goto missing_key
call "%~dp0prepare_portable.bat"
if errorlevel 1 goto failed
set "UPDATE_PY=%~dp0.app-venv\Scripts\python.exe"
if exist "%~dp0.app-venv\Scripts\pyinstaller.exe" goto build
echo 正在准备启动器打包工具...
"%~dp0tools\uv.exe" pip install --python "%UPDATE_PY%" pyinstaller
if errorlevel 1 goto failed
:build
echo [1/2] 正在重新打包启动器...
"%UPDATE_PY%" -X utf8 -m PyInstaller -y --distpath "%~dp0." --workpath "%TEMP%\AIChatMemoryLauncher-build" "%~dp0AIChatMemoryLauncher.spec"
if errorlevel 1 goto failed
echo [2/2] 正在生成签名清单、OneBot 组件和版本快照...
"%UPDATE_PY%" -X utf8 "%~dp0publish_update.py" --archive "%UPDATE_ARCHIVE%" --key "%UPDATE_ARCHIVE%\签名密钥\release-signing-key.xml"
if errorlevel 1 goto failed
echo.
echo 联网更新已生成，本脚本不会上传服务器。
echo 发布目录：%UPDATE_ARCHIVE%\网站上传\jingban
echo 先上传 components 和 releases 的新增内容，最后替换 latest.json。
echo 请保管好签名密钥；不要上传原项目或“签名密钥”目录。
pause
exit /b 0
:missing_key
echo 找不到原来的签名私钥，请恢复“鲸伴更新\签名密钥”后重试。
echo 不要随意生成新密钥，旧客户端依赖原来的公钥验证更新。
:failed
echo 生成失败，请查看上面的错误。请勿上传不完整的发布内容。
pause
exit /b 1
