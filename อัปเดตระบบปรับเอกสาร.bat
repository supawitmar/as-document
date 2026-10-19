@echo off
rem Update this program to the latest released version from GitHub (double-click).
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\package\update.ps1" -Online -Dest "%~dp0."
