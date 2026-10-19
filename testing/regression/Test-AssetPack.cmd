@echo off
rem Builds the x86 programs Test-NativeAssetsBank.py and Test-AssetPrepare.py run: the
rem module's art pack decoder with a reader of a whole pack, and a stand-in for the
rem installer's preparation, as the module and the installer are compiled (MSVC, x86).
setlocal
call "E:\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvarsall.bat" x86 >nul
if errorlevel 1 exit /b %errorlevel%
pushd "%~dp0..\.."
if not exist build\asset-pack-test mkdir build\asset-pack-test
cl /nologo /O2 /fp:strict /MT /TC /c third_party\lzma-sdk\LzmaDec.c /Fobuild\asset-pack-test\LzmaDec.obj
if errorlevel 1 goto done
cl /nologo /O2 /std:c++17 /EHsc /MT /W3 /D_CRT_SECURE_NO_WARNINGS /Isrc\controller-native /Ithird_party\lzma-sdk ^
  testing\regression\asset_pack_harness.cpp src\controller-native\K1AssetPack.cpp build\asset-pack-test\LzmaDec.obj ^
  /Fobuild\asset-pack-test\ /Febuild\asset-pack-test\asset-pack-check.exe
if errorlevel 1 goto done
cl /nologo /O2 /std:c++17 /EHsc /MT /W3 testing\regression\asset_prepare_harness.cpp ^
  /Fobuild\asset-pack-test\ /Febuild\asset-pack-test\asset-prepare-check.exe
:done
set RESULT=%errorlevel%
popd
exit /b %RESULT%
