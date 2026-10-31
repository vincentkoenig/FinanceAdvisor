# FinTrack als ein Container: baut das React-Frontend und startet Flask mit Gunicorn.
# Die Datenbank liegt außerhalb (Neon), der Container selbst speichert keine Daten.
#
# Bauen:    docker build -t fintrack .
# Starten:  docker run --env-file .env -p 8000:8000 fintrack
# Nötige Umgebungsvariablen: SECRET_KEY, DATABASE_URL, OPENAI_API_KEY, TAVILY_API_KEY,
# COINGECKO_API_KEY, ADMIN_API_KEY (siehe README). Nie ins Image kopieren.

# ─── 1. Frontend bauen ───
FROM node:24-slim AS frontend
WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ─── 2. Laufzeit: Python mit der App und dem gebauten Frontend ───
# Gleiche Python-Version wie in der CI
FROM python:3.12-slim

# APP_ENV=production: Cookies nur über HTTPS, echte Client-IP aus dem Proxy-Header,
# SECRET_KEY ist Pflicht (siehe fintrack/config.py)
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_ENV=production \
    PORT=8000

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py ./
COPY fintrack ./fintrack
COPY migrations ./migrations
COPY --from=frontend /build/frontend/dist ./frontend/dist
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh

# Ohne root-Rechte laufen; instance/ nur für eine lokale SQLite-Datenbank
RUN useradd --create-home --uid 10001 fintrack \
    && mkdir -p instance && chown fintrack instance \
    && chmod +x /usr/local/bin/docker-entrypoint.sh
USER fintrack

EXPOSE 8000

# /healthz fasst die Datenbank nicht an (siehe fintrack/health.py)
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=4)"

ENTRYPOINT ["docker-entrypoint.sh"]
