@echo off
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0upload_esp8266.ps1" %*
exit /b %ERRORLEVEL%
