@echo off
rem Opens the app window. Files dragged onto this file are added to the list.
start "" pythonw "%~dp0app.py" %*
