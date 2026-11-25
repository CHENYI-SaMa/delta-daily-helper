Unicode true
ManifestDPIAware true
Name "三角洲每日助手"
OutFile "三角洲每日助手安装包.exe"
InstallDir "$PROGRAMFILES64\DeltaForceDaily"
RequestExecutionLevel admin

!include "MUI2.nsh"
!define MUI_ICON "icon.ico"
!define MUI_UNICON "icon.ico"
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "SimpChinese"

Section "Main" SEC01
  SetOutPath "$INSTDIR"
  File /oname=三角洲每日助手.exe "app_payload.exe"
  WriteUninstaller "$INSTDIR\Uninstall.exe"

  CreateDirectory "$SMPROGRAMS\DeltaForceDaily"
  CreateShortcut "$SMPROGRAMS\DeltaForceDaily\三角洲每日助手.lnk" "$INSTDIR\三角洲每日助手.exe"
  CreateShortcut "$SMPROGRAMS\DeltaForceDaily\卸载三角洲每日助手.lnk" "$INSTDIR\Uninstall.exe"
  CreateShortcut "$DESKTOP\三角洲每日助手.lnk" "$INSTDIR\三角洲每日助手.exe"

  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\DeltaForceDaily" "DisplayName" "三角洲每日助手"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\DeltaForceDaily" "UninstallString" "$INSTDIR\Uninstall.exe"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\DeltaForceDaily" "QuietUninstallString" "$INSTDIR\Uninstall.exe /S"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\DeltaForceDaily" "InstallLocation" "$INSTDIR"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\DeltaForceDaily" "DisplayIcon" "$INSTDIR\三角洲每日助手.exe"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\DeltaForceDaily" "Publisher" "DeltaForceDaily"
  WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\DeltaForceDaily" "NoModify" 1
  WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\DeltaForceDaily" "NoRepair" 1
SectionEnd

Section "Uninstall"
  ExecWait 'taskkill /IM "三角洲每日助手.exe" /F' $R0

  Delete "$INSTDIR\三角洲每日助手.exe"
  Delete "$INSTDIR\Uninstall.exe"
  RMDir "$INSTDIR"

  Delete "$SMPROGRAMS\DeltaForceDaily\三角洲每日助手.lnk"
  Delete "$SMPROGRAMS\DeltaForceDaily\卸载三角洲每日助手.lnk"
  RMDir "$SMPROGRAMS\DeltaForceDaily"
  Delete "$DESKTOP\三角洲每日助手.lnk"

  RMDir /r "$LOCALAPPDATA\DeltaForceNative"

  DeleteRegKey HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\DeltaForceDaily"
SectionEnd
