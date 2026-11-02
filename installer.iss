#ifndef PayloadDir
  #error Use build_installer.py to supply a verified clean payload.
#endif
#ifndef AppVersion
  #error Missing application version.
#endif
#ifndef AppFileVersion
  #define AppFileVersion AppVersion + ".0.0"
#endif
#ifndef SourceRoot
  #error Missing public source directory.
#endif
#ifndef BundledPython
  #error Missing bundled interpreter path.
#endif

[Setup]
AppId={{537F9B18-37A8-4373-9EFA-8673D85870DC}
AppName=鲸伴
AppVersion={#AppVersion}
AppVerName=鲸伴 v{#AppVersion}
AppPublisher=鲸伴
VersionInfoVersion={#AppFileVersion}
DefaultDirName={localappdata}\Programs\JingBan
DefaultGroupName=鲸伴
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
DisableWelcomePage=no
DisableDirPage=no
DisableProgramGroupPage=yes
WizardStyle=modern
SetupIconFile={#SourceRoot}\assets\jingban-icon.ico
UninstallDisplayIcon={app}\鲸伴.exe
OutputBaseFilename=鲸伴-v{#AppVersion}-安装包
Compression=lzma2/max
SolidCompression=yes
CloseApplications=yes
RestartApplications=no
SetupLogging=yes

[Languages]
Name: "chinesesimp"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "快捷方式："

[Files]
Source: "{#PayloadDir}\*"; DestDir: "{app}"; Excludes: "app_settings.json"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#PayloadDir}\app_settings.json"; DestDir: "{app}"; Flags: onlyifdoesntexist uninsneveruninstall

[Icons]
Name: "{group}\鲸伴"; Filename: "{app}\鲸伴.exe"; WorkingDir: "{app}"
Name: "{autodesktop}\鲸伴"; Filename: "{app}\鲸伴.exe"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\鲸伴.exe"; WorkingDir: "{app}"; Description: "启动鲸伴"; Flags: nowait postinstall skipifsilent

[Code]
procedure CurStepChanged(CurStep: TSetupStep);
var
  ExitCode: Integer;
  PythonExe, Parameters: String;
begin
  if CurStep = ssPostInstall then
  begin
    PythonExe := ExpandConstant('{app}\{#BundledPython}');
    Parameters := '-I "' + ExpandConstant('{app}\portable_runtime.py') + '"';
    if not Exec(PythonExe, Parameters, ExpandConstant('{app}'), SW_HIDE,
                ewWaitUntilTerminated, ExitCode) then
      RaiseException('运行环境初始化未能启动，请检查安装文件是否完整。');
    if ExitCode <> 0 then
      RaiseException('运行环境初始化失败，请查看安装日志后重试。');
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  RunValue, AppRoot: String;
  Position: Integer;
begin
  if CurUninstallStep = usUninstall then
  begin
    AppRoot := Lowercase(AddBackslash(ExpandConstant('{app}')));
    if RegQueryStringValue(HKCU, 'Software\Microsoft\Windows\CurrentVersion\Run', '鲸伴', RunValue) then
    begin
      RunValue := Lowercase(RunValue);
      Position := Pos(AppRoot + 'runtime\python\', RunValue);
      if ((Position = 1) or (Position = 2)) and
         (Pos(AppRoot + 'app_startup.py', RunValue) > 0) then
        RegDeleteValue(HKCU, 'Software\Microsoft\Windows\CurrentVersion\Run', '鲸伴');
    end;
  end;
end;
