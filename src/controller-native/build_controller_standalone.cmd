@echo off
rem Builds the standalone controller module, build\controller-standalone\kmrp-controller.dll:
rem KMRP's controller support with its own files embedded, and nothing else of KMRP
rem (no interface scaling, no engine recipe, no memory or movie fixes). Packaged by
rem tools\build_controller_kpatch.py as "KOTOR 1 Native Controller Mod + Xbox HUD.kpatch".
setlocal
set VC=E:\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvarsall.bat
if not exist "%VC%" exit /b 1
call "%VC%" x86 >nul
if errorlevel 1 exit /b %errorlevel%
pushd "%~dp0..\.."
pwsh -NoProfile -ExecutionPolicy Bypass -File tools\prepare_sdl3.ps1
if errorlevel 1 exit /b %errorlevel%
if not exist build\controller-standalone mkdir build\controller-standalone
python tools\build_controller_assets.py
if errorlevel 1 exit /b %errorlevel%
python tools\build_controller_kpatch.py --write-def build\controller-standalone\controller-exports.def
if errorlevel 1 exit /b %errorlevel%
rc /nologo /Ibuild\controller-standalone /fobuild\controller-standalone\controller-assets.res build\controller-standalone\controller-assets.rc
if errorlevel 1 exit /b %errorlevel%
cl /nologo /Brepro /std:c++17 /O2 /fp:strict /EHsc /MT /LD /DKMRP_CONTROLLER_STANDALONE ^
  /Ibuild\controller-standalone /Isrc\controller-native /Ibuild\deps\SDL3-3.4.16\include ^
  src\controller-native\K1ControllerStandalone.cpp ^
  src\controller-native\K1NativeJoystick.cpp src\controller-native\K1ControllerBackend.cpp ^
  src\controller-native\K1ControllerLayout.cpp src\controller-native\K1Rumble.cpp ^
  src\controller-native\K1XboxHud.cpp ^
  src\controller-native\vendor\K1XboxControls.cpp src\controller-native\vendor\K1XboxControlsXInput.cpp ^
  build\controller-standalone\controller-assets.res ^
  /Fobuild\controller-standalone\ /Febuild\controller-standalone\kmrp-controller.dll ^
  /link /Brepro xinput.lib user32.lib gdi32.lib cabinet.lib bcrypt.lib ^
  /DEF:build\controller-standalone\controller-exports.def /INCREMENTAL:NO ^
  /MAP:build\controller-standalone\kmrp-controller.map
set RESULT=%errorlevel%
popd
exit /b %RESULT%
