@echo off
chcp 65001 > nul
echo Parando servicos do Atlas Urbano...
powershell -ExecutionPolicy Bypass -File "%~dp0scripts\stop.ps1"
pause
