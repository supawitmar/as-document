@echo off
rem Manual update (no internet): install the version in THIS extracted folder over the program on this computer.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\package\update.ps1"
