@echo off
rem Installs the app on this computer (checks requirements, creates the desktop icon).
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1" %*
