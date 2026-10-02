@echo off
rem Builds the KMRP controller module from the tracked source in this directory.
rem
rem Project sources are under version control; SDL headers are hash-pinned.
rem The build no longer reads
rem the clone of Saul0097's repository under build/research/, which was the only
rem copy of 900 lines of KMRP code and 842 lines of KMRP modifications to his.
rem
rem vendor/ holds Saul0097's sources as modified by KMRP (MIT; see
rem THIRD_PARTY_NOTICES.md and the .diff beside the vendored binaries).
setlocal
set VC=E:\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvarsall.bat
if not exist "%VC%" (
    echo Could not find vcvarsall.bat at "%VC%".
    echo Edit VC in this script to match your Visual Studio Build Tools install.
    exit /b 1
)
call "%VC%" x86 >nul
if errorlevel 1 exit /b %errorlevel%

pwsh -NoProfile -ExecutionPolicy Bypass -File "%~dp0..\..\tools\prepare_sdl3.ps1"
if errorlevel 1 exit /b %errorlevel%

pushd "%~dp0"
rem /I. so the vendor sources still find K1NativeJoystick.h, which now sits a
rem directory above them. Their own header resolves from the includer's folder.
cl /nologo /Brepro /O2 /EHsc /MT /LD /I. /I"..\..\build\deps\SDL3-3.4.16\include" ^
   K1NativeJoystick.cpp K1ControllerBackend.cpp K1ControllerLayout.cpp K1Rumble.cpp K1KpmApplier.cpp K1PopupFit.cpp K1GrantedPopup.cpp K1KeyboardNavigation.cpp vendor\K1XboxControls.cpp vendor\K1XboxControlsXInput.cpp ^
   xinput.lib gdi32.lib user32.lib ^
   /link /Brepro /DEF:exports.def /OUT:kmrp-controller.module /INCREMENTAL:NO
set RC=%errorlevel%
popd
exit /b %RC%
