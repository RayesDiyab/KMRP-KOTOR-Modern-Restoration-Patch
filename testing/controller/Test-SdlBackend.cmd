@echo off
setlocal
call "E:\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvarsall.bat" x86 >nul
if errorlevel 1 exit /b %errorlevel%
cd /d "%~dp0..\.."
cl /nologo /EHsc /MT /I"src\controller-native" /I"build\deps\SDL3-3.4.16\include" testing\controller\Test-SdlBackend.cpp user32.lib /Fo"build\deps\Test-SdlBackend.obj" /Fe"build\deps\Test-SdlBackend.exe"
if errorlevel 1 exit /b %errorlevel%
build\deps\Test-SdlBackend.exe
exit /b %errorlevel%
