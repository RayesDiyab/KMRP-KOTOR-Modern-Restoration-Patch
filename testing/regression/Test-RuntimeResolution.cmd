@echo off
setlocal
call "E:\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvarsall.bat" x86 >nul
if errorlevel 1 exit /b %errorlevel%
pushd "%~dp0..\.."
if not exist build\native-preview mkdir build\native-preview
cl /nologo /EHsc /std:c++17 /MT testing\regression\Test-RuntimeResolution.cpp ^
  /Fobuild\native-preview\ /Febuild\native-preview\runtime-resolution-check.exe
if errorlevel 1 exit /b %errorlevel%
build\native-preview\runtime-resolution-check.exe build\native-preview\kmrp-native-preview.dll
set RESULT=%errorlevel%
popd
exit /b %RESULT%
