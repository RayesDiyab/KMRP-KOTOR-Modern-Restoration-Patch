@echo off
rem What build_kmrp.ps1 counts as the compiler for its module step's fingerprint: the versions
rem vcvarsall selects, the include and library paths it sets, the four environment variables
rem cl and link read for extra options, and where cl and link are, whose files the build
rem then hashes.
setlocal
set VC=E:\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvarsall.bat
if not exist "%VC%" exit /b 1
call "%VC%" x86 >nul 2>nul
if errorlevel 1 exit /b %errorlevel%
echo tools=%VCToolsVersion%
echo sdk=%WindowsSDKVersion%
echo ucrt=%UCRTVersion%
echo include=%INCLUDE%
echo lib=%LIB%
echo CL=%CL%
echo _CL_=%_CL_%
echo LINK=%LINK%
echo _LINK_=%_LINK_%
where cl
if errorlevel 1 exit /b %errorlevel%
where link
exit /b %errorlevel%
