@echo off
setlocal
cd /d "%~dp0"
call "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvarsall.bat" x86 >nul
if errorlevel 1 exit /b 1
if not exist out mkdir out
cl /nologo /O2 /GS- /MT /W3 /utf-8 /LD islandko.c /Fo:out\ /Fe:out\version.dll /link /DEF:islandko.def /DLL /MACHINE:X86 /OPT:REF /OPT:ICF
exit /b %errorlevel%
