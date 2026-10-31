@echo off
rem Builds the standalone module, build\native-runtime\kmrp-native.dll: KMRP's core,
rem controller, movie and memory code with the engine recipe embedded, and its art pack,
rem build\native-runtime\kmrp-assets.pack, which the installer writes beside it
rem (tools\build_native_assets.py, tools\kmrp_pack.py). KMRP's patch carries the module
rem (tools\build_native_kpatch.py); which of its hooks are installed is the patch's
rem business, not the module's.
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
rem The art pack is made again when its version (tools\build_native_assets.py,
rem ASSETS_VERSION) is not the one recorded, or when there is none.
if exist build\native-runtime\font-style-assets.version findstr /x "8" build\native-runtime\font-style-assets.version >nul || del build\native-runtime\kmrp-assets.pack build\native-runtime\font-style-assets.version 2>nul
if not exist build\native-runtime\font-style-assets.version if exist build\native-runtime\kmrp-assets.pack del build\native-runtime\kmrp-assets.pack
if not exist build\native-runtime\kmrp-assets.pack python tools\build_native_assets.py
if errorlevel 1 exit /b %errorlevel%
python tools\build_native_kpatch.py --write-def build\native-runtime\native-exports.def
if errorlevel 1 exit /b %errorlevel%
rem The LZMA SDK's decoder (third_party\lzma-sdk, public domain), for the art pack.
cl /nologo /O2 /fp:strict /MT /TC /c ^
  third_party\lzma-sdk\LzmaDec.c /Fobuild\native-runtime\LzmaDec.obj
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
cl /nologo /O2 /fp:strict /MT /TC /DKMRP_EMBEDDED /D_CRT_SECURE_NO_WARNINGS /c ^
  macos\tools\kmrp-swoophud.c /Fobuild\native-runtime\kmrp-swoophud.obj
if errorlevel 1 exit /b %errorlevel%
cl /nologo /O2 /fp:strict /MT /TC /DKMRP_EMBEDDED /D_CRT_SECURE_NO_WARNINGS /c ^
  macos\tools\kmrp-guiadapt.c /Fobuild\native-runtime\kmrp-guiadapt.obj
if errorlevel 1 exit /b %errorlevel%
rem A mod's copy of any 2DA KMRP changes, merged three ways (kmrp-merge.c, kmrp-2da.h).
cl /nologo /O2 /fp:strict /MT /TC /DKMRP_EMBEDDED /D_CRT_SECURE_NO_WARNINGS /c ^
  macos\tools\kmrp-merge.c /Fobuild\native-runtime\kmrp-merge.obj
if errorlevel 1 exit /b %errorlevel%
rem /MP compiles the sources on every core at once (2026-10-27); each source compiles
rem the same as alone and /Brepro keeps the output byte for byte the same.
cl /nologo /MP /Brepro /std:c++17 /O2 /fp:strict /EHsc /MT /LD /DKMRP_NATIVE_RUNTIME ^
  /Ibuild\native-runtime /Isrc\controller-native /Ithird_party\lzma-sdk /Ibuild\deps\SDL3-3.4.16\include ^
  src\controller-native\K1RuntimeResolution.cpp src\controller-native\K1RuntimeEngine.cpp ^
  src\controller-native\K1RuntimeAssets.cpp src\controller-native\K1PartyRosterGui.cpp src\controller-native\K1AssetPack.cpp ^
  src\controller-native\K1RuntimeLayout.cpp ^
  src\controller-native\K1TextLayout.cpp src\controller-native\K1TextRows.cpp ^
  src\controller-native\K1TextOptions.cpp src\controller-native\K1HudOptions.cpp src\controller-native\K1PcHud.cpp ^
  src\controller-native\K1OffscreenFrame.cpp ^
  src\controller-native\K1NativeJoystick.cpp src\controller-native\K1ControllerBackend.cpp ^
  src\controller-native\K1ControllerLayout.cpp src\controller-native\K1Rumble.cpp src\controller-native\K1ButtonRemap.cpp ^
  src\controller-native\K1PopupFit.cpp src\controller-native\K1GrantedPopup.cpp ^
  src\controller-native\K1KeyboardNavigation.cpp ^
  src\controller-native\vendor\K1XboxControls.cpp src\controller-native\vendor\K1XboxControlsXInput.cpp ^
  build\native-runtime\kmrp-guiblend.obj ^
  build\native-runtime\kmrp-abilityicons.obj build\native-runtime\kmrp-gameart.obj ^
  build\native-runtime\kmrp-swoophud.obj build\native-runtime\kmrp-guiadapt.obj build\native-runtime\kmrp-merge.obj ^
  build\native-runtime\LzmaDec.obj ^
  /Fobuild\native-runtime\ /Febuild\native-runtime\kmrp-native.dll ^
  /link /Brepro user32.lib gdi32.lib bcrypt.lib crypt32.lib ^
  /DEF:build\native-runtime\native-exports.def /INCREMENTAL:NO ^
  /MAP:build\native-runtime\kmrp-native.map
set RESULT=%errorlevel%
popd
exit /b %RESULT%
