@echo off
chcp 65001 > nul
title Atlas Urbano de Paulo Afonso - Localhost

cd /d "%~dp0"
echo ========================================================
echo     Iniciando Atlas Urbano de Paulo Afonso...
echo ========================================================

if not exist ".venv\Scripts\python.exe" (
    echo Criando ambiente virtual...
    python -m venv .venv
    call .venv\Scripts\pip install -r backend\requirements.txt
)

start "" http://127.0.0.1:5173/

.\.venv\Scripts\python.exe scripts\serve.py

pause
