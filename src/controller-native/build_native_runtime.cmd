@echo off
rem Builds the standalone module, build\native-runtime\kmrp-native.dll: KMRP's core,
rem controller, movie and memory code with the engine recipe and the resource bank
rem embedded. Both standalone packages carry it (tools\build_native_kpatch.py); which
rem of its hooks are installed is the package's business, not the module's.
setlocal
set VC=E:\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvarsall.bat
if not exist "%VC%" exit /b 1
call "%VC%" x86 >nul
if errorlevel 1 exit /b %errorlevel%
pushd "%~dp0..\.."
pwsh -NoProfile -ExecutionPolicy Bypass -File tools\prepare_sdl3.ps1
if errorlevel 1 exit /b %errorlevel%
python tools\build_native_engine.py
if errorlevel 1 exit /b %errorlevel%
if not exist build\native-runtime\native-assets.bin python tools\build_native_assets.py
if errorlevel 1 exit /b %errorlevel%
python tools\build_native_kpatch.py --write-def build\native-runtime\native-exports.def
if errorlevel 1 exit /b %errorlevel%
rc /nologo /Ibuild\native-runtime /fobuild\native-runtime\native-assets.res build\native-runtime\native-assets.rc
if errorlevel 1 exit /b %errorlevel%
cl /nologo /O2 /fp:strict /MT /TC /DKMRP_GUI_EMBEDDED /c ^
  macos\tools\kmrp-guiblend.c /Fobuild\native-runtime\kmrp-guiblend.obj
if errorlevel 1 exit /b %errorlevel%
cl /nologo /O2 /fp:strict /MT /TC /DKMRP_EMBEDDED /D_CRT_SECURE_NO_WARNINGS /c ^
  macos\tools\kmrp-abilityicons.c /Fobuild\native-runtime\kmrp-abilityicons.obj
if errorlevel 1 exit /b %errorlevel%
cl /nologo /O2 /fp:strict /MT /TC /DKMRP_EMBEDDED /D_CRT_SECURE_NO_WARNINGS /c ^
  macos\tools\kmrp-gameart.c /Fobuild\native-runtime\kmrp-gameart.obj
if errorlevel 1 exit /b %errorlevel%
cl /nologo /Brepro /std:c++17 /O2 /fp:strict /EHsc /MT /LD /DKMRP_NATIVE_RUNTIME ^
  /Ibuild\native-runtime /Isrc\controller-native /Ibuild\deps\SDL3-3.4.16\include ^
  src\controller-native\K1RuntimeResolution.cpp src\controller-native\K1RuntimeEngine.cpp ^
  src\controller-native\K1RuntimeAssets.cpp src\controller-native\K1RuntimeLayout.cpp ^
  src\controller-native\K1RuntimeNvidia.cpp ^
  src\controller-native\K1NativeJoystick.cpp src\controller-native\K1ControllerBackend.cpp ^
  src\controller-native\K1ControllerLayout.cpp src\controller-native\K1Rumble.cpp ^
  src\controller-native\K1PopupFit.cpp src\controller-native\K1GrantedPopup.cpp ^
  src\controller-native\K1KeyboardNavigation.cpp ^
  src\controller-native\vendor\K1XboxControls.cpp src\controller-native\vendor\K1XboxControlsXInput.cpp ^
  build\native-runtime\kmrp-guiblend.obj ^
  build\native-runtime\kmrp-abilityicons.obj build\native-runtime\kmrp-gameart.obj ^
  build\native-runtime\native-assets.res ^
  /Fobuild\native-runtime\ /Febuild\native-runtime\kmrp-native.dll ^
  /link /Brepro xinput.lib user32.lib gdi32.lib cabinet.lib bcrypt.lib crypt32.lib ^
  /DEF:build\native-runtime\native-exports.def /INCREMENTAL:NO ^
  /MAP:build\native-runtime\kmrp-native.map
set RESULT=%errorlevel%
popd
exit /b %RESULT%
