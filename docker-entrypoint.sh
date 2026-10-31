#!/bin/sh
# Start im Container: erst ausstehende Datenbank-Migrationen, dann der Server.
# Genau ein Gunicorn-Worker, damit der eingebaute Scheduler
# (täglicher Lauf) nicht mehrfach parallel läuft. Mehrere Threads, damit eine lange
# KI-Anfrage (Chat, Analyse) die anderen Seiten nicht blockiert.
set -e

python -m flask --app "fintrack:create_app()" upgrade-db

exec gunicorn app:app \
    --bind "0.0.0.0:${PORT:-8000}" \
    --workers 1 \
    --threads 4 \
    --timeout 120 \
    --access-logfile -
