#!/bin/sh
# Aktualisiert FinTrack auf dem Server: neuesten Stand von main holen, Image bauen,
# Container neu starten und warten, bis er gesund ist.
#
# Aufgerufen von GitHub Actions über einen eigenen Deploy-Schlüssel. Der Schlüssel ist in
# /root/.ssh/authorized_keys auf genau diesen Befehl beschränkt (command="..."), kann also
# nichts anderes auf dem Server ausführen. Von Hand: sh /opt/fintrack/src/deploy/server-deploy.sh
set -eu

SRC=/opt/fintrack/src
COMPOSE="docker compose -f $SRC/deploy/compose.yaml"

cd "$SRC"
git fetch --quiet origin main
# Nur vorwärts: hat jemand auf dem Server etwas verändert, bricht das hier ab statt es zu überschreiben
git merge --ff-only --quiet origin/main
echo "Stand: $(git log --oneline -1)"

$COMPOSE build fintrack
$COMPOSE up -d fintrack

# Auf den Healthcheck aus dem Dockerfile warten (prüft /healthz, ohne die Datenbank zu wecken)
container=$($COMPOSE ps -q fintrack)
for attempt in $(seq 1 36); do
    status=$(docker inspect --format '{{.State.Health.Status}}' "$container")
    if [ "$status" = "healthy" ]; then
        echo "FinTrack läuft (healthy)."
        # Alte, nicht mehr benutzte Images aufräumen, damit die Festplatte nicht vollläuft
        docker image prune -f > /dev/null
        exit 0
    fi
    sleep 5
done

echo "FinTrack ist nach 3 Minuten nicht gesund. Letzte Log-Zeilen:"
$COMPOSE logs --tail 40 fintrack
exit 1
