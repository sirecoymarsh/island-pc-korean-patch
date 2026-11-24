@echo off
setlocal
cd /d "%~dp0"
call "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvarsall.bat" x86 >nul 2>nul
if not exist out mkdir out
cl /nologo /O1 /MT /W3 dlltest.c /Fo:out\ /Fe:out\dlltest.exe
exit /b %errorlevel%
