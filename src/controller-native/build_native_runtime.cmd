@echo off
setlocal
set VC=E:\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvarsall.bat
if not exist "%VC%" exit /b 1
call "%VC%" x86 >nul
if errorlevel 1 exit /b %errorlevel%
pushd "%~dp0..\.."
python tools\build_native_engine.py
if errorlevel 1 exit /b %errorlevel%
if not exist build\native-runtime\native-assets.bin python tools\build_native_assets.py
if errorlevel 1 exit /b %errorlevel%
rc /nologo /Ibuild\native-runtime /fobuild\native-runtime\native-assets.res build\native-runtime\native-assets.rc
if errorlevel 1 exit /b %errorlevel%
cl /nologo /O2 /fp:strict /MT /TC /DKMRP_GUI_EMBEDDED /DKMRP_NO_CONTROLLER /c ^
  macos\tools\kmrp-guiblend.c /Fobuild\native-runtime\kmrp-guiblend.obj
if errorlevel 1 exit /b %errorlevel%
cl /nologo /Brepro /std:c++17 /O2 /fp:strict /EHsc /MT /LD /DKMRP_NATIVE_RUNTIME ^
  /Ibuild\native-runtime src\controller-native\K1RuntimeResolution.cpp ^
  src\controller-native\K1RuntimeEngine.cpp src\controller-native\K1RuntimeAssets.cpp src\controller-native\K1RuntimeLayout.cpp ^
  src\controller-native\K1KeyboardNavigation.cpp build\native-runtime\kmrp-guiblend.obj ^
  build\native-runtime\native-assets.res ^
  /Fobuild\native-runtime\ /Febuild\native-runtime\kmrp-native.dll ^
  /link /Brepro user32.lib cabinet.lib bcrypt.lib /EXPORT:KmrpAllowRuntimeResolutionK1 /EXPORT:KmrpResolutionRequestedK1 ^
  /EXPORT:KmrpResolutionObservedK1 /EXPORT:KeyboardNavigateK1 ^
  /EXPORT:KeyboardListBoundaryK1 /EXPORT:KeyboardKeepFocusK1 ^
  /EXPORT:NativeFreeSaveBufferK1 /EXPORT:KmrpPrepareResourcesK1 ^
  /EXPORT:KmrpPanelLayoutStartK1 /EXPORT:KmrpPanelControlK1 ^
  /EXPORT:KmrpPanelDestroyedK1 /EXPORT:KmrpControlDestroyedK1 /INCREMENTAL:NO
set RESULT=%errorlevel%
popd
exit /b %RESULT%
