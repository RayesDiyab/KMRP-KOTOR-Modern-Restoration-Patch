@echo off
setlocal
set VC=E:\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvarsall.bat
if not exist "%VC%" exit /b 1
call "%VC%" x86 >nul
if errorlevel 1 exit /b %errorlevel%
pushd "%~dp0..\.."
if not exist build\native-preview mkdir build\native-preview
cl /nologo /Brepro /O2 /EHsc /MT /LD src\controller-native\K1RuntimeResolution.cpp ^
  src\controller-native\K1KeyboardNavigation.cpp ^
  /Fobuild\native-preview\ /Febuild\native-preview\kmrp-native-preview.dll ^
  /link /Brepro /EXPORT:KmrpAllowRuntimeResolutionK1 /EXPORT:KmrpResolutionRequestedK1 ^
  /EXPORT:KmrpResolutionObservedK1 /EXPORT:KeyboardNavigateK1 ^
  /EXPORT:KeyboardListBoundaryK1 /EXPORT:KeyboardKeepFocusK1 ^
  /EXPORT:NativeFreeSaveBufferK1 /INCREMENTAL:NO
set RESULT=%errorlevel%
popd
exit /b %RESULT%
