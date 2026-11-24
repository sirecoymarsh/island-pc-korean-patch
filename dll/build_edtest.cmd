@echo off
rem build-detection probes for tools\test_edition_dll.py (out\edtest\*.exe)
setlocal
cd /d "%~dp0"
call "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvarsall.bat" x86 >nul 2>nul
if not exist out\edtest mkdir out\edtest
rc /nologo /fo out\edtest\ver68.res edtest_ver68.rc || exit /b 1
rc /nologo /fo out\edtest\ver80.res edtest_ver80.rc || exit /b 1
cl /nologo /O1 /MT /W3 edtest.c /Fo:out\edtest\ /Fe:out\edtest\edtest_plain.exe || exit /b 1
cl /nologo /O1 /MT /W3 /DBIND edtest.c /Fo:out\edtest\ /Fe:out\edtest\edtest_bind.exe || exit /b 1
cl /nologo /O1 /MT /W3 edtest.c out\edtest\ver68.res /Fo:out\edtest\ /Fe:out\edtest\edtest_v68.exe || exit /b 1
cl /nologo /O1 /MT /W3 /DBIND edtest.c out\edtest\ver68.res /Fo:out\edtest\ /Fe:out\edtest\edtest_v68_bind.exe || exit /b 1
cl /nologo /O1 /MT /W3 edtest.c out\edtest\ver80.res /Fo:out\edtest\ /Fe:out\edtest\edtest_v80.exe || exit /b 1
cl /nologo /O1 /MT /W3 /DBIND edtest.c out\edtest\ver80.res /Fo:out\edtest\ /Fe:out\edtest\edtest_v80_bind.exe || exit /b 1
exit /b 0
