@echo off
title FinTrack Server
cd /d "%~dp0"
call .venv\Scripts\activate

rem Datenbank per Migration auf den neuesten Stand bringen (legt sie beim ersten Start an)
python -m flask --app "fintrack:create_app()" upgrade-db
if errorlevel 1 (
    echo Datenbank-Migration fehlgeschlagen - Server wird nicht gestartet.
    pause
    exit /b 1
)

rem Frontend bauen: Flask liefert frontend\dist unter /app aus
if not exist frontend\node_modules call npm ci --prefix frontend
call npm run build --prefix frontend
if errorlevel 1 (
    echo Frontend-Build fehlgeschlagen - Server wird nicht gestartet.
    pause
    exit /b 1
)

start "" http://127.0.0.1:5000/app/
python app.py

pause