@echo off
cd /d "%~dp0"
powershell -ExecutionPolicy Bypass -File ".\scripts\run.ps1"
pause
