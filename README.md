# FinTrack (ehemals FinanceAdvisor) 💹


Eine KI-gestützte Finanz-Web-App mit **Flask**-API, **React**-Frontend und **OpenAI**. Verwalte dein Investment-Portfolio, führe ein Haushaltsbuch, chatte mit einem KI-Finanzberater und lass dir strukturierte Portfolio-Analysen erstellen — installierbar als mobile App (PWA), live auf einem eigenen Server, und über einen eigenen MCP-Server auch für Claude Desktop nutzbar.

**Live:** https://fintrack.vincentkoenig.ai *(Konten legt der Betreiber an)*

## Features

### 🏠 Übersicht
- Gesamtvermögen aus live bewertetem Depot und kumuliertem Cash-Bestand, dazu die Veränderung seit gestern (Käufe und Verkäufe herausgerechnet) und der Gewinn seit Kauf
- „Zu tun“: fällige Sparpläne direkt ausführen, geplante mit ihrem nächsten Termin
- Monatsfluss: wohin das Einkommen des Monats geht (Fixkosten, Variabel, Sparplan, frei übrig), dazu Tages-Update der KI, größte Positionen und letzte Buchungen

### 📊 Portfolio & Watchlist
- Aktien, ETFs, Kryptowährungen und Edelmetalle hinzufügen, kaufen und verkaufen
- Assets per Name, Symbol oder ISIN suchen und aus einer Ergebnisliste auswählen — Euro-Börsen (Xetra zuerst) stehen oben, Kryptowährungen werden als Euro-Paar angeboten (BTC-EUR), „Gold“ und „Silber“ meinen das Edelmetall
- Live-Preise kommen über **yfinance** in der Handelswährung des Titels und werden mit dem aktuellen Wechselkurs in Euro umgerechnet — Euro-Titel wie SAP.DE oder BTC-EUR bleiben unverändert, Kurse in Pence (London) werden in Pfund umgerechnet
- Automatische Neuberechnung des durchschnittlichen Kaufpreises bei weiteren Käufen
- Historische Schlusskurse werden beim Hinzufügen eines neuen Assets für 1 Jahr geladen und in der Handelswährung gespeichert, dazu die täglichen Wechselkurse — im Chart wird jeder Tag mit seinem eigenen Wechselkurs in Euro umgerechnet
- Ein täglicher Lauf (abends nach US-Börsenschluss) lädt die letzten 7 Tage neu und überschreibt sie: Zwischenstände werden so durch Schlusskurse ersetzt und ausgefallene Läufe automatisch nachgeholt. Danach werden Dividenden (mit dem Wechselkurs am Ex-Tag) verbucht und die KI-Insights erzeugt
- Interaktiver Portfolio-Wert-Chart mit wählbaren Zeiträumen (1W / 1M / YTD / 1J / Max), aus den echten Käufen und Verkäufen rekonstruiert: Jeder Tag zählt die Stückzahl, die an diesem Tag im Depot lag, auch von inzwischen verkauften Positionen. An Wochenenden und Feiertagen gilt der letzte Schlusskurs
- Die Entwicklung im gewählten Zeitraum rechnet Käufe und Verkäufe heraus, damit ein Kauf nicht als Gewinn erscheint
- Sortierbare Positionstabelle (auf dem Handy als Liste); ein Klick auf eine Position öffnet Kauf und Verkauf
- Aufteilung nach Anlageart (ETFs, Aktien, Krypto, Edelmetalle) als Balken oder Ring
- Reiter für Watchlist (beobachten, aus der Watchlist kaufen), Transaktionen, Sparpläne (anlegen, ausführen, löschen) und Dividenden

### 💰 Haushaltsbuch
- Einnahmen, Fixkosten und variable Ausgaben in einer dreistufigen Kategorienstruktur (Einkommen / Fixkosten / Variable Ausgaben), jeweils mit anpassbaren Haupt- und Unterkategorien
- Standardkategorien werden für jeden neuen Nutzer automatisch angelegt und können danach frei bearbeitet oder gelöscht werden
- Einmalige und wiederkehrende Buchungen (z.B. monatliches Gehalt oder Miete) mit optionalem Enddatum — wiederkehrende Einträge werden pro Monat live berechnet, statt in der Datenbank dupliziert zu werden
- Monatsweise Navigation: „Übrig im Monat“ mit Monatsfluss, Ausgaben nach Hauptkategorie mit Tagesschnitt
- Wiederkehrende Buchungen lassen sich pausieren und fortsetzen; eine pausierte Buchung zählt in den Monaten vor ihrer Pause weiter mit
- Vollständige Buchungsliste mit Löschfunktion (mit Rückfrage)
- Kumulierter Cash-Bestand über alle Monate seit der ersten Buchung, der auch in die Home-Übersicht einfließt

### 🤖 KI-Finanzberater (Chat)
- Chat mit einem GPT-4o-mini-gestützten Finanzberater als eigene Seite; Antworten mit Listen, Tabellen und Links werden formatiert, ohne dass HTML aus der Antwort in die Seite gelangt
- **Function Calling** — die KI ruft eigenständig Live-Preise ab (Aktien, Krypto, Edelmetalle) und verarbeitet auch mehrere gleichzeitige Tool-Aufrufe in einem Zug korrekt
- **Websuche über Tavily** — die KI sucht bei Bedarf aktuelle Marktnachrichten, statt sich nur auf veraltetes Trainingswissen zu verlassen
- Adaptives Antwortformat (kurze Antworten bei Preisfragen, Tabellen bei Vergleichen, Beispiele bei Erklärungen) — kein starres Einheitsformat
- Persistenter Chatverlauf in der Datenbank, mit einem Sliding Window der letzten 20 Nachrichten, um Tokenkosten und Kontextlänge im Griff zu behalten
- Personalisierte Antworten basierend auf Risikoprofil, Erfahrung, Budget und Anlagehorizont des Nutzers

### 📈 KI-Portfolio-Analyse
- Analyse auf Knopfdruck mittels **Pydantic Structured Output** (`response_format`)
- Liefert strukturiertes JSON: Risikobewertung, Diversifikationsscore, Zusammenfassung, Empfehlungen und Allokation
- Der Gesamtwert des Portfolios wird serverseitig berechnet (nicht dem LLM überlassen), um numerische Genauigkeit sicherzustellen
- Alle vorherigen Analysen werden gespeichert und können auf der Analyse-Seite eingesehen werden

### 👤 Nutzerverwaltung
- Login mit E-Mail und gehashtem Passwort (`werkzeug.security`), Anmeldung über ein sicheres Session-Cookie (Flask-Login: HttpOnly, SameSite, in Produktion nur über HTTPS, 30 Tage gültig)
- Jeder Nutzer sieht und ändert nur seine eigenen Daten — automatisch für jede Route geprüft
- Schutz gegen Durchprobieren: Begrenzung der Login-, Registrierungs- und Code-Versuche (Flask-Limiter), Verifizierungscode nach 5 Fehlversuchen gesperrt, einheitliche Fehlermeldung bei falscher E-Mail oder falschem Passwort
- Registrierung abschaltbar (`ALLOW_REGISTRATION`), Konten und Passwörter alternativ per Kommandozeile
- **Export und Import aller eigenen Daten** als JSON-Datei (Einstellungen → Meine Daten) — unabhängig von der Datenbank, damit ein Umzug auf einen anderen Server oder Anbieter jederzeit möglich ist
- Persönliche Einstellungen: Risikoprofil, Anlageerfahrung, monatliches Budget, Anlagehorizont
- Nutzerprofil-Daten fließen in jeden System-Prompt der KI ein, für personalisierte Beratung
- Dunkles und helles Design, pro Gerät gespeichert

### 🔌 MCP-Server
- Eigenständiger Model-Context-Protocol-Server, der FinTrack-Daten für MCP-fähige Clients wie Claude Desktop bereitstellt
- Drei Tools: `get_portfolio_summary` (aktuelle Bestände), `get_budget_status` (monatliche Einnahmen/Ausgaben/Saldo), `add_transaction` (neue Haushaltsbuch-Buchung direkt aus einem Chat-Gespräch heraus anlegen)
- Nutzt dieselben SQLAlchemy-Modelle und dieselbe Budget-Berechnungslogik wie die Web-App (`budget_logic.py`) — keine doppelte Geschäftslogik
- Läuft lokal gegen dieselbe Datenbank und löst absolute Pfade zur Laufzeit auf, damit es unabhängig davon funktioniert, aus welchem Arbeitsverzeichnis Claude Desktop den Server startet
- Details siehe [`mcp_server/`](./mcp_server)

### 📱 Mobile & PWA
- Eine Oberfläche für Laptop und Handy: auf dem Handy eine untere Navigation mit „Mehr“-Blatt, Listen statt breiter Tabellen, eingeklappte Nebenbereiche und Dialoge als Blatt von unten
- Installierbar als Progressive Web App mit eigenem Icon (auch „maskable“ und für den iPhone-Homescreen)
- Eigener Service Worker: speichert nur Programmdateien, nie Konto- oder Depotdaten; ohne Netz erscheint eine Offline-Seite, nach einem Deploy der Hinweis „Neue Version verfügbar“

### 🎨 UI / Design
- Design „Tanne“: Mint und Waldgrün, nachts Wald mit Jade; die Leitkarte jeder Seite ist eine grüne Farbfläche, Bernstein nur für Fälliges
- Alle Farben als Design-Tokens (CSS Custom Properties) mit Werten für Hell und Dunkel
- Toast-Benachrichtigungen, Ladezustände, erklärende leere Zustände und „Erneut versuchen“ bei Ladefehlern

### ☁️ Deployment
- Live als **Docker**-Container auf einem eigenen Server hinter **Traefik** (automatisches HTTPS), läuft unter **Gunicorn** mit einem einzigen Worker (nötig, damit der Scheduler nicht mehrfach parallel läuft) — kein Kaltstart
- **PostgreSQL** im Produktivbetrieb, die App fällt lokal automatisch auf **SQLite** zurück, wenn keine `DATABASE_URL`-Umgebungsvariable gesetzt ist — derselbe Code für lokale Entwicklung und Produktion
- Geheimnisse (OpenAI-, CoinGecko-, Tavily-API-Keys, Datenbank-URL) werden über Umgebungsvariablen verwaltet, niemals im Repository gespeichert

## Tech Stack

![Python](https://img.shields.io/badge/Python-3776AB?style=flat&logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-000000?style=flat&logo=flask&logoColor=white)
![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-D71F00?style=flat&logo=sqlalchemy&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-4169E1?style=flat&logo=postgresql&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-003B57?style=flat&logo=sqlite&logoColor=white)
![OpenAI](https://img.shields.io/badge/OpenAI_API-412991?style=flat&logo=openai&logoColor=white)
![React](https://img.shields.io/badge/React-20232A?style=flat&logo=react&logoColor=61DAFB)
![TypeScript](https://img.shields.io/badge/TypeScript-3178C6?style=flat&logo=typescript&logoColor=white)
![Vite](https://img.shields.io/badge/Vite-646CFF?style=flat&logo=vite&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-2496ED?style=flat&logo=docker&logoColor=white)

- **Flask** — REST-API-Backend, liefert außerdem das gebaute Frontend aus
- **SQLAlchemy** — ORM, PostgreSQL im Live-Betrieb / SQLite für die lokale Entwicklung
- **OpenAI API** — GPT-4o-mini für Chat (Function Calling) und Portfolio-Analyse (Structured Output)
- **Tavily** — Echtzeit-Websuche für aktuelle Finanznachrichten, als LLM-Tool eingebunden
- **Pydantic** — Structured-Output-Parsing für die Portfolio-Analyse
- **yfinance** — Kursdaten für Aktien, ETFs und Edelmetalle, historische Preise und Asset-Suche per Name
- **CoinGecko API** — Kryptowährungskurse
- **APScheduler** + **GitHub Actions** — täglicher Lauf für Kurse, Wechselkurse, Dividenden und Insights
- **MCP (Model Context Protocol)** — eigenständiger Server, der App-Daten als Tools für Claude Desktop bereitstellt
- **Gunicorn** — Produktions-WSGI-Server
- **werkzeug** — Passwort-Hashing und Sicherheit
- **python-dotenv** — sichere Verwaltung der API-Keys
- **React 19, TypeScript, Vite** — Frontend unter `/app`, mit React Router und TanStack Query; Diagramme als eigenes SVG, Styling mit reinem CSS und Design-Tokens
- **Vitest, Testing Library, MSW** — Frontend-Tests gegen eine nachgebaute API
- **Web App Manifest + eigener Service Worker** — PWA mit Offline-Seite und Update-Hinweis

## Projektstruktur

```
FinTrack/
├── app.py                    # Einstiegspunkt für Gunicorn/lokal: baut die App und startet den Scheduler
├── fintrack/                  # Die eigentliche App als Paket
│   ├── __init__.py             # create_app(): Konfiguration, Datenbank, Blueprints
│   ├── config.py               # Einstellungen aus Umgebungsvariablen, Datenbank-URL
│   ├── extensions.py           # Gemeinsame Objekte: Datenbank, Migrationen, Login, Limiter, OpenAI-Client
│   ├── api.py                  # Eingabeprüfung (Pydantic) und einheitliche JSON-Fehler der API
│   ├── database.py             # flask upgrade-db: Migrationen ausführen, alte Datenbanken übernehmen
│   ├── models.py               # SQLAlchemy-Modelle + Pydantic-Schemas für Structured Output
│   ├── jobs.py                 # Täglicher Lauf (Kurse, Dividenden, Insights) im Hintergrund, Scheduler
│   ├── health.py               # Statuspunkt /healthz für Docker und Überwachung
│   ├── spa.py                  # Liefert das React-Frontend unter /app aus, / und alte Seitenadressen leiten dorthin
│   ├── auth/                   # Registrierung, Login/Session, Verifizierung, Profil, CLI (create-user, set-password)
│   ├── account/                # Export und Import aller eigenen Daten
│   ├── portfolio/              # Assets, Positionen, Watchlist, Sparpläne, Dividenden, KI-Analyse
│   ├── budget/                 # Haushaltsbuch: Routen + Berechnungslogik (auch vom MCP-Server genutzt)
│   ├── chat/                   # KI-Chat mit Function-Calling-Tools
│   ├── contracts/              # Verträge: Routen + Berechnung von Laufzeit und Kündigungsfrist
│   ├── imports/                # Import von Kontoumsätzen (CSV) mit Abgleich und Dubletten-Schutz
│   ├── insights/               # Täglicher KI-Insight
│   ├── admin/                  # Geschützte Endpoints zum manuellen Anstoßen der Jobs
│   └── market/                 # Marktdaten (yfinance, CoinGecko, Tavily) + zentraler Preis-Service
├── frontend/                     # React-Frontend (React, TypeScript, Vite), ausgeliefert unter /app
├── migrations/                   # Alembic-Migrationen (Schemaänderungen der Datenbank)
├── tests/                        # pytest: Unit- und Integrationstests (u.a. Zugriffsschutz für jede Route)
├── requirements.txt              # Abhängigkeiten der Haupt-App, alle Versionen fest gepinnt
├── requirements-dev.txt          # Zusätzlich für Tests (pytest, MCP-SDK)
├── Dockerfile                    # Container mit Frontend-Build und Gunicorn (Start über docker-entrypoint.sh)
├── deploy/                       # Eigener Server: Compose-Datei, Deploy-Skript, Einrichtung (deploy/README.md)
├── start.bat                     # Windows-Starter — migriert die Datenbank, baut das Frontend, startet den Server und öffnet den Browser
├── mcp_server/
│   ├── server.py                  # MCP-Server, stellt Portfolio-/Budget-Tools für Claude Desktop bereit
│   └── requirements.txt            # Abhängigkeiten der App plus MCP-SDK
├── docs/                          # Backup-Anleitung (BACKUP.md), Screenshots, Demo-Video
└── .github/workflows/             # CI-Tests (inkl. PostgreSQL) und nächtliches Datenbank-Backup
```

## API-Übersicht

Alle Routen liegen unter `/api/v1` und antworten mit JSON. Persönliche Daten liegen unter `/api/v1/me/...` — welcher Nutzer gemeint ist, erkennt der Server am Anmelde-Cookie, die URLs enthalten nie eine User-ID. Eingaben werden mit Pydantic geprüft; Fehler kommen einheitlich als `{"error": "...", "fields": {...}}` auf Deutsch zurück.

| Methode | Route | Beschreibung |
|--------|-------|-------------|
| `POST` | `/auth/register` | Registrieren (nur wenn `ALLOW_REGISTRATION=1`), Code per E-Mail |
| `POST` | `/auth/verify-email` | E-Mail mit Code bestätigen, danach angemeldet |
| `POST` | `/auth/resend-verification` | Neuen Code anfordern |
| `POST` | `/auth/login` · `/auth/logout` | Anmelden (setzt Session-Cookie) · Abmelden |
| `GET` · `PUT` | `/me` · `/me/settings` | Eigenes Profil · Anlage-Einstellungen speichern |
| `GET` | `/assets/search?query=` | Assets per Name, Symbol oder ISIN suchen — Ergebnisliste, bekannte Assets und Euro-Börsen zuerst, legt nichts an |
| `POST` | `/assets` | Ausgewählten Suchtreffer (`symbol`, `name`) als Asset anlegen und ein Jahr Kurse laden (201, bei vorhandenem Asset 200) |
| `GET` | `/assets/<id>` | Asset mit Live-Preis |
| `GET` · `POST` | `/me/positions` | Positionen mit Live-Preis · Kauf erfassen (bestehende Position wird ergänzt) |
| `POST` | `/me/positions/<asset_id>/buy` · `/sell` | Nachkauf · Verkauf |
| `GET` | `/me/asset-transactions` | Kauf-/Verkaufshistorie |
| `GET` | `/me/portfolio/history` | Täglicher Portfolio-Wert in Euro (`[{date, value}]`) vom ersten Kauf bis heute |
| `GET` · `POST` | `/me/analyses` | Bisherige KI-Analysen · neue Analyse erstellen |
| `GET` · `POST` · `DELETE` | `/me/watchlist` · `/me/watchlist/<asset_id>` | Watchlist |
| `GET` · `POST` | `/me/savings-plans` | Sparpläne |
| `DELETE` · `POST` | `/me/savings-plans/<id>` · `/execute` | Sparplan löschen · ausführen |
| `GET` | `/me/dividends` | Verbuchte Dividenden |
| `GET` · `POST` | `/me/categories` | Budgetkategorien |
| `DELETE` | `/me/categories/<id>` | Kategorie löschen (nicht möglich, solange Buchungen daran hängen) |
| `POST` | `/me/categories/init-defaults` | Standardkategorien nachträglich anlegen |
| `GET` · `POST` | `/me/transactions` | Buchungen (optional `?month=JJJJ-MM`) · neue Buchung |
| `DELETE` · `POST` | `/me/transactions/<id>` · `/toggle-pause` | Buchung löschen · wiederkehrende Buchung pausieren/fortsetzen |
| `GET` | `/me/budget/summary` | Cash-Bestand und aktueller Monat |
| `POST` | `/me/import/bank/preview` | CSV-Export der Bank lesen (Feld `file`, optional `mapping`): Umsätze mit Status `new` / `covered` (deckt eine wiederkehrende Buchung ab) / `duplicate` und Kategorievorschlag, speichert nichts |
| `POST` | `/me/import/bank/commit` | Bestätigte Umsätze als Buchungen übernehmen (alles oder nichts, schon importierte werden übersprungen) |
| `GET` · `POST` | `/me/contracts` | Verträge mit Status, Kündigungstag und Kosten pro Monat/Jahr (sortiert nach Frist) · neuer Vertrag |
| `PUT` · `DELETE` | `/me/contracts/<id>` | Vertrag bearbeiten · löschen |
| `GET` | `/me/contracts/suggestions` | Regelmäßige Abbuchungen aus importierten Umsätzen (monatlich bis jährlich, ähnlicher Betrag), die noch kein Vertrag sind |
| `POST` · `DELETE` | `/me/contracts/<id>/cancel` | Als gekündigt markieren (ohne `end_date` zum nächstmöglichen Termin) · Kündigung zurücknehmen |
| `POST` · `DELETE` | `/me/contracts/<id>/booking` | Mit dem Haushaltsbuch verknüpfen (`category_id`: neue Fixkosten-Buchung, Beitrag anteilig pro Monat · `transaction_id`: vorhandene wiederkehrende Buchung) · Verknüpfung lösen |
| `POST` · `GET` | `/me/chat` · `/me/chat/history` | KI-Chat · Verlauf |
| `GET` | `/me/insight` | Letzter täglicher KI-Insight |
| `GET` | `/me/export` | Alle eigenen Daten als JSON-Datei herunterladen |
| `POST` | `/me/import` | Exportdatei in ein leeres Konto einspielen (alles oder nichts) |
| `POST` | `/admin/run-daily-jobs` | Kompletten täglichen Lauf im Hintergrund starten (202, bei laufendem Job 409; Header `X-Admin-Key`) |
| `POST` | `/admin/update-prices` · `/admin/check-dividends` · `/admin/generate-insights` | Einzelne Jobs im Hintergrund starten (Header `X-Admin-Key`) |
| `GET` | `/admin/jobs/status` | Zustand und Ergebnis des letzten Laufs (Header `X-Admin-Key`) |
| `POST` | `/admin/assets/<id>/prices` | Historischen Preis manuell eintragen (Header `X-Admin-Key`) |

## Erste Schritte

**1. Repository klonen**
```bash
git clone https://github.com/vincentkoenig/FinanceAdvisor.git
cd FinanceAdvisor
```

**2. Abhängigkeiten installieren**
```bash
pip install -r requirements.txt
```

**3. `.env`-Datei anlegen**
```
OPENAI_API_KEY=dein_openai_api_key
COINGECKO_API_KEY=dein_coingecko_api_key
TAVILY_API_KEY=dein_tavily_api_key
```
> API-Keys gibt es unter [platform.openai.com](https://platform.openai.com/api-keys), [coingecko.com](https://www.coingecko.com/en/api) und [tavily.com](https://tavily.com)
>
> `DATABASE_URL` ist optional — ist sie nicht gesetzt, nutzt die App automatisch eine lokale SQLite-Datenbank.

Optionale Variablen:

| Variable | Zweck |
|---|---|
| `SECRET_KEY` | Signiert die Anmelde-Cookies. **In Produktion Pflicht** (sonst startet die App nicht). Lokal empfohlen, sonst ist man nach jedem Neustart abgemeldet. Erzeugen mit `python -c "import secrets; print(secrets.token_hex(32))"` |
| `ALLOW_REGISTRATION=1` | Erlaubt neue Konten über die Startseite. Standard: geschlossen — Konten dann per `create-user` anlegen (siehe unten). |
| `ADMIN_API_KEY` | Schlüssel für die Routen unter `/api/v1/admin/...` (Header `X-Admin-Key`). Ohne ihn sind diese Endpoints gesperrt. |
| `FLASK_DEBUG=1` | Debug-Modus beim lokalen Start mit `python app.py`. Wird automatisch abgeschaltet, wenn der Server im Netzwerk erreichbar ist. |
| `FLASK_HOST=0.0.0.0` | Server im lokalen Netzwerk erreichbar machen, z.B. für Tests vom Handy. Standard ist nur dieser PC (`127.0.0.1`). |

Einen manuellen Job startest du dann so (er läuft im Hintergrund, das Ergebnis steht danach unter `/api/v1/admin/jobs/status`):
```bash
curl -X POST -H "X-Admin-Key: dein_schluessel" http://localhost:5000/api/v1/admin/update-prices
```

**4. Datenbank anlegen und App starten**
```bash
python -m flask --app "fintrack:create_app()" upgrade-db
python app.py
```
`upgrade-db` legt die lokale SQLite-Datenbank im `instance/`-Ordner an bzw. bringt sie per Migration auf den neuesten Stand. Alternativ unter Windows: Doppelklick auf `start.bat` — das erledigt beides und öffnet den Browser. Der Preis-Scheduler startet im Hintergrund.

**Schema ändern:** Nach einer Änderung in `fintrack/models.py` eine Migration erzeugen, prüfen und mit committen:
```bash
python -m flask --app "fintrack:create_app()" db migrate -m "kurze Beschreibung"
```
`upgrade-db` bricht ab, wenn Datenbank und Modelle nach der Migration nicht übereinstimmen — eine vergessene Migration fällt so beim Start auf, statt still Fehler zu verursachen.

**Konto anlegen bzw. Passwort zurücksetzen** (solange die Registrierung geschlossen ist). Das Passwort wird verdeckt abgefragt; `set-password` meldet das Konto zusätzlich auf allen Geräten ab:
```bash
python -m flask --app "fintrack:create_app()" create-user deine@email.de
python -m flask --app "fintrack:create_app()" set-password deine@email.de
```

**5. Frontend bauen und im Browser öffnen**

Das Frontend (React, TypeScript, Vite) liegt in `frontend/` und braucht Node 24 (siehe `.node-version`). `start.bat` baut es unter Windows automatisch; von Hand:
```bash
cd frontend
npm ci
npm run build    # baut nach frontend/dist; Flask liefert das unter http://localhost:5000/app/ aus
npm run dev      # Entwicklungsserver auf http://localhost:5280/app/, leitet /api an Flask auf Port 5000 weiter
npm test         # Tests (Vitest, Testing Library, MSW)
```
Danach http://localhost:5000 öffnen (leitet nach `/app/`). Auf dem Smartphone lässt sich die App über „App installieren“ (Chrome) bzw. „Zum Home-Bildschirm“ (Safari) als PWA installieren.

**Als Container (Docker)**

Das `Dockerfile` baut Frontend und Backend in ein Image; die Datenbank bleibt außerhalb (z.B. Neon). Die Umgebungsvariablen kommen zur Laufzeit dazu, nie ins Image:
```bash
docker build -t fintrack .
docker run --env-file .env -p 8000:8000 fintrack   # http://localhost:8000/app/
```
Beim Start laufen zuerst die Migrationen, dann Gunicorn mit einem Worker (wegen des Schedulers) und vier Threads. `GET /healthz` meldet, ob die App läuft, ohne die Datenbank zu wecken; `GET /healthz?db=1` prüft zusätzlich die Datenbankverbindung.

**6. (Optional) MCP-Server mit Claude Desktop verbinden**

Die komplette Anleitung dazu findet sich in [`mcp_server/`](./mcp_server) — kurz zusammengefasst: einen Eintrag in der `claude_desktop_config.json` anlegen, der auf `mcp_server/server.py` verweist und den Python-Interpreter der eigenen virtuellen Umgebung nutzt, danach Claude Desktop neu starten.

## Deployment

Die App läuft unter https://fintrack.vincentkoenig.ai auf einem eigenen VPS (Hostinger, Frankfurt) — Aufbau und Einrichtung siehe [`deploy/README.md`](./deploy/README.md):
- **Docker**-Container (`Dockerfile`) hinter dem vorhandenen **Traefik**, der das HTTPS-Zertifikat automatisch holt; beim Start laufen zuerst die Migrationen, dann Gunicorn
- **Automatisches Ausrollen:** Nach jedem Merge auf `main` laufen die Tests, danach aktualisiert GitHub Actions den Server über einen Deploy-Schlüssel, der nur das Deploy-Skript ausführen darf, und prüft `/healthz?db=1` von außen
- **PostgreSQL**-Datenbank bei [Neon](https://neon.tech) in Frankfurt (kostenloser Tarif), verbunden über die Umgebungsvariable `DATABASE_URL`
- Geheimnisse in `/opt/fintrack/.env` auf dem Server (nur für root lesbar) und als GitHub-Secrets, nie im Repository
- Täglicher Lauf (Kurse, Dividenden, Insights) über den eingebauten Scheduler um 22:30 Uhr deutscher Zeit; GitHub Actions ([`daily-jobs.yml`](./.github/workflows/daily-jobs.yml), 21:30 UTC) startet ihn zusätzlich als Absicherung über `/api/v1/admin/run-daily-jobs` (Repository-Secret `ADMIN_API_KEY`, derselbe Wert wie auf dem Server) — eine Sperre verhindert doppelte Läufe
- Nächtliches, verschlüsseltes Datenbank-Backup mit automatischem Wiederherstellungstest über GitHub Actions — Einrichtung und Wiederherstellung siehe [`docs/BACKUP.md`](./docs/BACKUP.md)

## Was ich dabei gelernt habe

- Aufbau einer versionierten Flask-REST-API (`/api/v1`) mit über 30 Endpoints, Pydantic-Validierung und einheitlichen Fehlerantworten
- Integration von OpenAI Function Calling, damit die KI eigenständig Live-Daten abruft, im Web sucht (über Tavily) und auch mehrere gleichzeitige Tool-Aufrufe in einem Zug korrekt verarbeitet
- Nutzung von Pydantic Structured Output (`response_format`) für zuverlässiges, schema-konformes JSON von LLMs, während numerisch kritische Werte (wie der Gesamtportfoliowert) serverseitig berechnet statt der LLM-Arithmetik überlassen werden
- Entwurf einer relationalen SQLAlchemy-Datenbank mit 9 verknüpften Modellen, inklusive einer zweistufigen, selbstreferenzierenden Kategorienstruktur für das Haushaltsbuch
- Modellierung wiederkehrender Buchungen (Einnahmen/Ausgaben) als einzelne Datenbankzeilen, die beim Lesen pro Monat live ausgewertet werden, statt Zeilen zu duplizieren — dadurch keine Abhängigkeit von einem Scheduler zur Generierung
- Umsetzung sicherer Nutzerauthentifizierung mit Passwort-Hashing über `werkzeug`
- Ausführung von Hintergrundaufgaben mit APScheduler innerhalb eines Flask-App-Kontexts, inklusive Lückenfüllungs-Logik für verpasste Preisaktualisierungen, sowie Sicherstellung, dass der Scheduler auch unter Gunicorn statt dem Flask-Entwicklungsserver zuverlässig läuft
- Abruf und Abgleich von Live-Finanzdaten über mehrere APIs und Währungen hinweg (yfinance, CoinGecko, USD-→-EUR-Umrechnung), sowie Debugging von Chart-Artefakten durch Wochenenden/Feiertage und durch die Anwendung aktueller Wechselkurse auf historische Preise
- Iteratives Prompt Engineering mit adaptivem Antwortformat, durch direkten Vergleich mit ChatGPT-Ausgaben
- Verwaltung von LLM-Kontext und Tokenkosten mittels Sliding Window über den Chatverlauf
- Auslagerung gemeinsamer Geschäftslogik (`budget_logic.py`), sodass dieselbe Berechnung sowohl von der Flask-Web-App als auch von einem unabhängigen MCP-Server genutzt wird, ohne Logik zu duplizieren
- Aufbau und Debugging eines Model-Context-Protocol-Servers von Grund auf — Lösung von Flask-App-Kontext-Anforderungen, absoluter Pfadauflösung (ein MCP-Client kann den Server aus einem beliebigen Arbeitsverzeichnis heraus starten) und Auflösung des richtigen virtuellen-Umgebungs-Interpreters für Claude Desktop
- Umsetzung eines stimmigen, theme-fähigen „Glas"-Designsystems mittels CSS Custom Properties, `backdrop-filter` und geschichteter Transparenz über eine komplette mehrseitige Anwendung hinweg
- Nachträgliche Anpassung eines bestehenden Desktop-Layouts für Mobilgeräte: eine untere Tab-Leiste mit „Mehr"-Overflow-Menü, Umwandlung dichter Datentabellen in gestapelte Karten über `data-label`-Attribute und CSS, sowie Debugging realer Responsive-Probleme (ein fehlender Viewport-Meta-Tag, der sämtliche Media Queries stillschweigend deaktivierte; sich stapelndes Padding über verschachtelte Container hinweg)
- Umbau der App in eine installierbare Progressive Web App mit eigenem Manifest, generiertem Icon-Set und einem bewusst minimalen Service Worker (kein Offline-Caching, da die App auf Live-Kurs- und Chat-Daten angewiesen ist)
- Zusammenführung einer eigenständigen Seite (Watchlist) in eine bestehende Seite als Tab-Ansicht, ohne das Backend anzufassen, mit sorgfältiger Konsolidierung von Navigation und JavaScript-Zustand zur Vermeidung von Variablenkonflikten
- Migration von SQLite zu einem dualen SQLite/PostgreSQL-Setup, gesteuert über eine Umgebungsvariable, sowie Deployment auf Render mit Gunicorn, inklusive Behebung eines Schedulers, der beim Wechsel vom Flask-Entwicklungsserver zu einem WSGI-Server stillschweigend aufgehört hatte zu laufen
- Umzug von Render auf einen eigenen VPS ohne Kaltstart: Docker-Image mit Healthcheck, der die Datenbank nicht weckt, Traefik für HTTPS, abgesicherter Server (Firewall, nur SSH-Schlüssel) und automatisches Ausrollen über einen eingeschränkten Deploy-Schlüssel
- Trennung von Verantwortlichkeiten über mehrere Module hinweg (Routen, Modelle, Services, Scheduler, Tools, Budget-Logik)
- Schrittweiser Umbau der Jinja-Seiten zu einer React-/TypeScript-PWA in kleinen Pull Requests, parallel unter `/app`, bis zur Umstellung — mit klickbarem Prototyp vorab, Tests gegen eine nachgebaute API (MSW) und einem eigenen Service Worker, der bewusst keine Finanzdaten auf dem Gerät speichert
