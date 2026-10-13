@echo off
rem Download the BT.31 document system from GitHub and install it (needs internet).
powershell -NoProfile -ExecutionPolicy Bypass -Command "irm https://raw.githubusercontent.com/supawitmar/as-document/main/get.ps1 | iex"
