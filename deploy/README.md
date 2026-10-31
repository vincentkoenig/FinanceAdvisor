# FinTrack auf dem eigenen Server

FinTrack läuft als Docker-Container auf einem Hostinger-VPS (KVM 1, Frankfurt) hinter dem dort
vorhandenen Traefik, erreichbar unter https://fintrack.vincentkoenig.ai. Die Datenbank liegt
weiter bei Neon; der Server selbst speichert keine Nutzerdaten.

| Pfad auf dem Server | Inhalt |
|---|---|
| `/opt/fintrack/src` | Dieses Repository (Stand von `main`) |
| `/opt/fintrack/.env` | Geheimnisse und Einstellungen, nur für root lesbar (`chmod 600`), nie im Repository |
| `deploy/compose.yaml` | Container-Definition mit den Traefik-Labels |
| `deploy/server-deploy.sh` | Holt `main`, baut das Image, startet neu und wartet auf den Healthcheck |

## Automatisches Ausrollen

Nach jedem Merge auf `main` laufen erst die Tests, dann meldet sich GitHub Actions (Job `deploy`
in `.github/workflows/tests.yml`) mit einem eigenen Deploy-Schlüssel auf dem Server an. Der
Schlüssel ist in `/root/.ssh/authorized_keys` auf `server-deploy.sh` beschränkt und kann sonst
nichts ausführen. Zum Schluss prüft der Job `https://fintrack.vincentkoenig.ai/healthz?db=1`.
Fehlt das Secret `DEPLOY_SSH_KEY`, überspringt der Job das Ausrollen mit einer Warnung.

Von Hand ausrollen (auf dem Server): `sh /opt/fintrack/src/deploy/server-deploy.sh`

## Einmalige Einrichtung

Voraussetzungen: Docker mit Compose, Traefik mit Entrypoint `websecure` und Zertifikats-Resolver
`letsencrypt`, ein DNS-A-Eintrag für die Domain auf den Server, Firewall nur für 22/80/443.

1. Repository holen: `git clone https://github.com/vincentkoenig/FinanceAdvisor.git /opt/fintrack/src`
2. `/opt/fintrack/.env` anlegen (`chmod 600`) mit `SECRET_KEY` (`openssl rand -hex 32`),
   `DATABASE_URL`, `OPENAI_API_KEY`, `TAVILY_API_KEY`, `COINGECKO_API_KEY`, `ADMIN_API_KEY`,
   optional `RESEND_API_KEY`, und `SCHEDULER_ENABLED=0`, solange noch ein anderer Server den
   täglichen Lauf macht (sonst `1`).
3. Deploy-Schlüssel auf dem Server erzeugen und auf das Skript beschränken:
   ```bash
   ssh-keygen -t ed25519 -N "" -C "github-actions-deploy" -f /root/.ssh/fintrack_deploy
   echo "command=\"sh /opt/fintrack/src/deploy/server-deploy.sh\",no-port-forwarding,no-agent-forwarding,no-X11-forwarding,no-pty $(cat /root/.ssh/fintrack_deploy.pub)" >> /root/.ssh/authorized_keys
   ```
4. Den privaten Schlüssel (`cat /root/.ssh/fintrack_deploy`, alles von `-----BEGIN` bis `END-----`)
   als Repository-Secret `DEPLOY_SSH_KEY` hinterlegen (GitHub → Settings → Secrets and variables
   → Actions), danach auf dem Server löschen: `rm /root/.ssh/fintrack_deploy`.
5. Erster Start: `sh /opt/fintrack/src/deploy/server-deploy.sh`

Der Host-Schlüssel des Servers steht fest im Workflow
(Fingerabdruck `SHA256:nSGR3epb9tDBKuXH+ek0KRznPvDugCqHwx4ybj+K+sE`). Ändert er sich, etwa nach
einer Neuinstallation, bricht das Ausrollen ab, bis der Eintrag im Workflow angepasst ist.
