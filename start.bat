@echo off
title FinanceAdvisor Server
cd /d "%~dp0"
call .venv\Scripts\activate

rem Datenbank per Migration auf den neuesten Stand bringen (legt sie beim ersten Start an)
python -m flask --app "fintrack:create_app()" upgrade-db
if errorlevel 1 (
    echo Datenbank-Migration fehlgeschlagen - Server wird nicht gestartet.
    pause
    exit /b 1
)

start "" http://127.0.0.1:5000
python app.py

pause