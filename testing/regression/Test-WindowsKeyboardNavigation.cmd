@echo off
setlocal
call "E:\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvarsall.bat" x86 >nul
if errorlevel 1 exit /b %errorlevel%
cd /d "%~dp0..\.."
if not exist "build\tests\keyboard" mkdir "build\tests\keyboard"
cl /nologo /EHsc /std:c++17 /DKMRP_KEYBOARD_TEST ^
   src\controller-native\K1KeyboardNavigation.cpp testing\regression\Test-WindowsKeyboardNavigation.cpp ^
   /Fobuild\tests\keyboard\ /Febuild\tests\keyboard\navigation.exe
if errorlevel 1 exit /b %errorlevel%
build\tests\keyboard\navigation.exe
exit /b %errorlevel%
