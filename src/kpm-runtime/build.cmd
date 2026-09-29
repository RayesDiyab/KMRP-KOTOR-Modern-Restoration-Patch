@echo off
rem Builds KOTOR Patch Manager's Windows runtime for KMRP's installer, from the
rem submodule third_party\Kotor-Patch-Manager (git submodule update --init):
rem
rem   KotorPatcher.dll   the hook engine that reads patch_config.toml
rem                      (src\KotorPatcher, the six sources its .vcxproj compiles)
rem   binkw32.dll        KProxy, which the game loads in place of its own
rem                      binkw32.dll and which loads KotorPatcher.dll
rem                      (src\KProxy, forwarding every Bink export to
rem                      binkw32Hooked.dll)
rem
rem into build\kpm-runtime\. build_kmrp.ps1 runs this and embeds both.
rem
rem Built with cl directly rather than KPM's .vcxproj and publish.bat, for one
rem reason: those link the C runtime dynamically (/MD), so the DLL imports
rem MSVCP140.dll and VCRUNTIME140.dll and would not load on a machine without
rem the Visual C++ redistributable (measured 2026-09-29: the .vcxproj's Release
rem build imports ten DLLs). /MT leaves KERNEL32.dll as the only import, as for
rem kmrp-controller.module. The .vcxproj also links sqlite3.lib, which nothing
rem in these sources calls; it is left out.
setlocal
set VC=E:\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvarsall.bat
if not exist "%VC%" (
    echo Could not find vcvarsall.bat at "%VC%".
    echo Edit VC in this script to match your Visual Studio Build Tools install.
    exit /b 1
)
set ROOT=%~dp0..\..
set KPM=%ROOT%\third_party\Kotor-Patch-Manager
set P=%KPM%\src\KotorPatcher
set OUT=%ROOT%\build\kpm-runtime
if not exist "%P%\src\core\patcher.cpp" (
    echo KOTOR Patch Manager is missing at "%KPM%".
    echo Run: git submodule update --init
    exit /b 1
)
call "%VC%" x86 >nul
if errorlevel 1 exit /b %errorlevel%
if not exist "%OUT%\obj" mkdir "%OUT%\obj"

cl /nologo /Brepro /O2 /EHsc /MT /LD /std:c++17 /W3 ^
   /DWIN32 /DNDEBUG /DKOTORPATCHER_EXPORTS /D_WINDOWS /D_USRDLL ^
   /I"%P%\include" /I"%P%\include\wrappers" /I"%P%\external" ^
   /Fo"%OUT%\obj\\" ^
   "%P%\src\core\config_reader.cpp" "%P%\src\core\patcher.cpp" "%P%\src\core\trampoline.cpp" ^
   "%P%\src\core\wrapper_x86.cpp" "%P%\src\platform_win32.cpp" "%P%\src\dllmain.cpp" ^
   /link /Brepro /INCREMENTAL:NO /OUT:"%OUT%\KotorPatcher.dll" /IMPLIB:"%OUT%\obj\KotorPatcher.lib"
if errorlevel 1 exit /b %errorlevel%

cl /nologo /Brepro /O2 /MT /LD "%KPM%\src\KProxy\kproxy.cpp" /Fo"%OUT%\obj\kproxy.obj" ^
   /link /Brepro /INCREMENTAL:NO /DEF:"%KPM%\src\KProxy\bink_forwards.def" ^
   /OUT:"%OUT%\binkw32.dll" /IMPLIB:"%OUT%\obj\binkw32.lib"
exit /b %errorlevel%
