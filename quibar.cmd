@echo off
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0ops\docker\quibar.ps1" %*
exit /b %errorlevel%
