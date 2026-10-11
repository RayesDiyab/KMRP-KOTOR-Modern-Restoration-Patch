@echo off
rem Builds the x86 program Test-Xpress.py runs: the modules' decoder with the test's main.
setlocal
call "E:\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvarsall.bat" x86 >nul
if errorlevel 1 exit /b %errorlevel%
pushd "%~dp0..\.."
if not exist build\xpress-test mkdir build\xpress-test
cl /nologo /EHsc /std:c++17 /O2 /MT testing\regression\Test-Xpress.cpp src\controller-native\K1Xpress.cpp ^
  /Fobuild\xpress-test\ /Febuild\xpress-test\xpress-check.exe /link bcrypt.lib
set RESULT=%errorlevel%
popd
exit /b %RESULT%
