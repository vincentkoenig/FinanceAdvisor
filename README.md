# FinTrack (ehemals FinanceAdvisor) 💹


Eine KI-gestützte Finanz-Web-App auf Basis von **Flask** und **OpenAI**. Verwalte dein Investment-Portfolio, führe ein Haushaltsbuch, chatte mit einem KI-Finanzberater und lass dir strukturierte Portfolio-Analysen erstellen — installierbar als mobile App (PWA), live deployed auf Render, und über einen eigenen MCP-Server auch für Claude Desktop nutzbar.

**Live-Demo:** https://financeadvisor-snxz.onrender.com *(kostenloser Tarif — nach Inaktivität kann der erste Aufruf 30-60 Sekunden dauern, während der Server aufwacht)*

## Features

### 🏠 Home-Übersicht
- Zentrales Dashboard mit Portfolio-Wert, kumuliertem Cash-Bestand und Gesamtvermögen
- Kombiniert die live bewertete Portfolio-Position mit dem laufenden Saldo aus dem Haushaltsbuch

### 📊 Portfolio & Watchlist
- Aktien, ETFs, Kryptowährungen und Edelmetalle hinzufügen, kaufen und verkaufen
- Assets per Name, Symbol oder ISIN suchen und aus einer Ergebnisliste auswählen — Euro-Börsen (Xetra zuerst) stehen oben, Kryptowährungen werden als Euro-Paar angeboten (BTC-EUR), „Gold“ und „Silber“ meinen das Edelmetall
- Live-Preise kommen über **yfinance** in der Handelswährung des Titels und werden mit dem aktuellen Wechselkurs in Euro umgerechnet — Euro-Titel wie SAP.DE oder BTC-EUR bleiben unverändert, Kurse in Pence (London) werden in Pfund umgerechnet
- Automatische Neuberechnung des durchschnittlichen Kaufpreises bei weiteren Käufen
- Historische Schlusskurse werden beim Hinzufügen eines neuen Assets für 1 Jahr geladen und in der Handelswährung gespeichert, dazu die täglichen Wechselkurse — im Chart wird jeder Tag mit seinem eigenen Wechselkurs in Euro umgerechnet
- Ein täglicher Lauf (abends nach US-Börsenschluss) lädt die letzten 7 Tage neu und überschreibt sie: Zwischenstände werden so durch Schlusskurse ersetzt und ausgefallene Läufe automatisch nachgeholt. Danach werden Dividenden (mit dem Wechselkurs am Ex-Tag) verbucht und die KI-Insights erzeugt
- Interaktiver Portfolio-Wert-Chart mit wählbaren Zeiträumen (1W / 1M / YTD / 1J / Max), aus den echten Käufen und Verkäufen rekonstruiert: Jeder Tag zählt die Stückzahl, die an diesem Tag im Depot lag, auch von inzwischen verkauften Positionen. An Wochenenden und Feiertagen gilt der letzte Schlusskurs
- Sortierbare Positionstabelle (nach Titel, Kaufpreis, Positionswert, Gewinn/Verlust)
- Allokations-Donut-Chart mit dynamisch generierten, eindeutigen Farben pro Asset sowie dem Gesamtportfoliowert in der Mitte
- Privatsphäre-Umschalter — alle Beträge mit einem Klick hinter Sternchen verstecken
- **Watchlist als Tab auf derselben Seite** — Assets beobachten, die man noch nicht besitzt, Preis beim Hinzufügen im Vergleich zum aktuellen Preis sehen, und direkt aus der Watchlist heraus kaufen (das Asset wandert dabei automatisch ins Portfolio)

### 💰 Haushaltsbuch
- Einnahmen, Fixkosten und variable Ausgaben in einer dreistufigen Kategorienstruktur (Einkommen / Fixkosten / Variable Ausgaben), jeweils mit anpassbaren Haupt- und Unterkategorien
- Standardkategorien werden für jeden neuen Nutzer automatisch angelegt und können danach frei bearbeitet oder gelöscht werden
- Einmalige und wiederkehrende Buchungen (z.B. monatliches Gehalt oder Miete) mit optionalem Enddatum — wiederkehrende Einträge werden pro Monat live berechnet, statt in der Datenbank dupliziert zu werden
- Monatsweise Navigation mit Kennzahlen-Karten für Einnahmen, Fixkosten, Variable Ausgaben und Saldo
- Kategorien-Aufschlüsselung je Bereich mit Prozentanteil sowie ein Donut-Chart zur Visualisierung der Ausgaben nach Kategorie
- Vollständige Buchungsliste mit Löschfunktion
- Kumulierter Cash-Bestand über alle Monate seit der ersten Buchung, der auch in die Home-Übersicht einfließt

### 🤖 KI-Finanzberater (Chat)
- Chat mit einem GPT-4o-mini-gestützten Finanzberater, verfügbar als schwebendes Widget auf jeder Seite (Desktop) sowie als eigene Vollbild-Chat-Seite
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
- Registrierung und Login mit E-Mail und gehashtem Passwort (`werkzeug.security`), Anmeldung über ein sicheres Session-Cookie (Flask-Login: HttpOnly, SameSite, in Produktion nur über HTTPS, 30 Tage gültig)
- Jeder Nutzer sieht und ändert nur seine eigenen Daten — automatisch für jede Route geprüft
- Schutz gegen Durchprobieren: Begrenzung der Login-, Registrierungs- und Code-Versuche (Flask-Limiter), Verifizierungscode nach 5 Fehlversuchen gesperrt, einheitliche Fehlermeldung bei falscher E-Mail oder falschem Passwort
- Registrierung abschaltbar (`ALLOW_REGISTRATION`), Konten und Passwörter alternativ per Kommandozeile
- **Export und Import aller eigenen Daten** als JSON-Datei (Einstellungen → Meine Daten) — unabhängig von der Datenbank, damit ein Umzug auf einen anderen Server oder Anbieter jederzeit möglich ist
- Persönliche Einstellungen: Risikoprofil, Anlageerfahrung, monatliches Budget, Anlagehorizont
- Nutzerprofil-Daten fließen in jeden System-Prompt der KI ein, für personalisierte Beratung
- Dark-/Light-Mode-Umschalter, seiten- und sitzungsübergreifend gespeichert

### 🔌 MCP-Server
- Eigenständiger Model-Context-Protocol-Server, der FinTrack-Daten für MCP-fähige Clients wie Claude Desktop bereitstellt
- Drei Tools: `get_portfolio_summary` (aktuelle Bestände), `get_budget_status` (monatliche Einnahmen/Ausgaben/Saldo), `add_transaction` (neue Haushaltsbuch-Buchung direkt aus einem Chat-Gespräch heraus anlegen)
- Nutzt dieselben SQLAlchemy-Modelle und dieselbe Budget-Berechnungslogik wie die Web-App (`budget_logic.py`) — keine doppelte Geschäftslogik
- Läuft lokal gegen dieselbe Datenbank und löst absolute Pfade zur Laufzeit auf, damit es unabhängig davon funktioniert, aus welchem Arbeitsverzeichnis Claude Desktop den Server startet
- Details siehe [`mcp_server/`](./mcp_server)

### 📱 Mobile & PWA
- Durchgängig responsives Layout auf jeder Seite — untere Tab-Navigation unter 768px Bildschirmbreite, kartenbasierte Tabellen statt gequetschter Spalten, sowie ein „Mehr"-Menü für sekundäre Seiten
- Installierbar als Progressive Web App: eigenes App-Icon, Standalone-Anzeigemodus (ohne Browserleiste), nutzbar wie eine native App vom Homescreen aus
- Service Worker für die Installierbarkeit registriert (bewusst ohne aggressives Offline-Caching, da die App auf Live-Kurs- und Chat-Daten angewiesen ist)

### 🎨 UI / Design
- Eigenes „Liquid Glass"-Interface — durchscheinende, geblurrte Karten über einem sanften radialen Farbverlauf, konsistent auf jeder Seite, in Modals und im Chat-Widget
- Vollständig theme-fähig: alle Glas-Effekt-Farben sind als CSS-Variablen mit separaten Dark- und Light-Mode-Werten definiert
- Toast-Benachrichtigungen statt Browser-Alerts, Ladeindikatoren bei allen asynchronen Datenabrufen, clientseitige Validierung in jedem Formular

### ☁️ Deployment
- Live auf **Render**, läuft unter **Gunicorn** mit einem einzigen Worker (nötig, damit der Preis-Update-Scheduler nicht mehrfach parallel läuft)
- **PostgreSQL** im Produktivbetrieb, die App fällt lokal automatisch auf **SQLite** zurück, wenn keine `DATABASE_URL`-Umgebungsvariable gesetzt ist — derselbe Code für lokale Entwicklung und Produktion
- Geheimnisse (OpenAI-, CoinGecko-, Tavily-API-Keys, Datenbank-URL) werden über Umgebungsvariablen verwaltet, niemals im Repository gespeichert

## Tech Stack

![Python](https://img.shields.io/badge/Python-3776AB?style=flat&logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-000000?style=flat&logo=flask&logoColor=white)
![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-D71F00?style=flat&logo=sqlalchemy&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-4169E1?style=flat&logo=postgresql&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-003B57?style=flat&logo=sqlite&logoColor=white)
![OpenAI](https://img.shields.io/badge/OpenAI_API-412991?style=flat&logo=openai&logoColor=white)
![HTML5](https://img.shields.io/badge/HTML5-E34F26?style=flat&logo=html5&logoColor=white)
![JavaScript](https://img.shields.io/badge/JavaScript-F7DF1E?style=flat&logo=javascript&logoColor=black)
![Render](https://img.shields.io/badge/Render-46E3B7?style=flat&logo=render&logoColor=white)

- **Flask** — REST-API-Backend & HTML-Seiten-Rendering
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
- **Chart.js** — Portfolio-Wert-Chart, Allokations-Donut und Budget-Ausgaben-Donut
- **marked.js** — Markdown-Rendering für die KI-Chat-Antworten
- **Web App Manifest + Service Worker** — PWA-Installierbarkeit

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
│   ├── pages.py                # Routen, die die HTML-Seiten ausliefern
│   ├── auth/                   # Registrierung, Login/Session, Verifizierung, Profil, CLI (create-user, set-password)
│   ├── account/                # Export und Import aller eigenen Daten
│   ├── portfolio/              # Assets, Positionen, Watchlist, Sparpläne, Dividenden, KI-Analyse
│   ├── budget/                 # Haushaltsbuch: Routen + Berechnungslogik (auch vom MCP-Server genutzt)
│   ├── chat/                   # KI-Chat mit Function-Calling-Tools
│   ├── insights/               # Täglicher KI-Insight
│   ├── admin/                  # Geschützte Endpoints zum manuellen Anstoßen der Jobs
│   └── market/                 # Marktdaten (yfinance, CoinGecko, Tavily) + zentraler Preis-Service
├── frontend/                     # Neues React-Frontend (React, TypeScript, Vite), ausgeliefert unter /app
├── migrations/                   # Alembic-Migrationen (Schemaänderungen der Datenbank)
├── tests/                        # pytest: Unit- und Integrationstests (u.a. Zugriffsschutz für jede Route)
├── requirements.txt              # Abhängigkeiten der Haupt-App, alle Versionen fest gepinnt
├── requirements-dev.txt          # Zusätzlich für Tests (pytest, MCP-SDK)
├── start.bat                     # Windows-Starter — migriert die Datenbank, startet den Server und öffnet den Browser
├── mcp_server/
│   ├── server.py                  # MCP-Server, stellt Portfolio-/Budget-Tools für Claude Desktop bereit
│   └── requirements.txt            # Abhängigkeiten der App plus MCP-SDK
├── docs/                          # Backup-Anleitung (BACKUP.md), Screenshots, Demo-Video
├── .github/workflows/             # CI-Tests (inkl. PostgreSQL) und nächtliches Datenbank-Backup
├── static/
│   ├── manifest.json               # PWA-Manifest (Name, Icons, Anzeigemodus)
│   ├── service-worker.js            # Minimaler Service Worker für PWA-Installierbarkeit
│   ├── icons/                       # App-Icons (192px/512px, Standard + maskable)
│   ├── css/
│   │   ├── base.css                  # Gemeinsames Layout, Sidebar, Mobile-Nav, Glas-Effekt-Variablen, Modal, Chat-Widget
│   │   ├── home.css
│   │   ├── portfolio.css               # Enthält den Watchlist-Tab samt mobilem Karten-Layout
│   │   ├── budget.css
│   │   ├── chat.css
│   │   ├── analyse.css
│   │   └── settings.css
│   └── js/
│       ├── home.js
│       ├── portfolio.js                # Enthält die komplette Watchlist-Logik (aus der früheren eigenen Seite übernommen)
│       ├── budget.js
│       ├── chat.js
│       ├── analyse.js
│       ├── settings.js
│       ├── widget.js                    # Schwebendes Chat-Widget (nur Desktop)
│       ├── theme.js                      # Dark-/Light-Mode-Umschalter
│       ├── toast.js                      # Toast-Benachrichtigungs-Helfer
│       ├── mobile-nav.js                  # Mobile Bottom-Nav + „Mehr"-Menü-Umschalter
│       ├── utils.js                       # Gemeinsame Hilfsfunktionen: HTML maskieren, Markdown bereinigen, Farben, Umleitung bei abgelaufener Anmeldung
│       └── logout.js
└── templates/
    ├── index.html                # Login / Registrierung
    ├── home.html                  # Vermögensübersicht
    ├── portfolio.html              # Portfolio-Übersicht, Chart und Watchlist-Tab
    ├── budget.html                  # Haushaltsbuch
    ├── chat.html                     # Vollbild-Chat-Oberfläche
    ├── analyse.html                   # Portfolio-Analyse & Verlauf
    └── settings.html                   # Nutzerprofil-Einstellungen, Export und Import der Daten
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

**5. Im Browser öffnen**
```
http://localhost:5000
```
Auf dem Smartphone bietet Chrome an, die App über „Zum Startbildschirm hinzufügen" bzw. den Installations-Prompt als PWA zu installieren.

**Neues Frontend (im Aufbau):** Das neue React-Frontend (React, TypeScript, Vite) liegt in `frontend/` und läuft unter `/app`, die bisherigen Seiten bleiben bis zum Ende des Umbaus unter `/`. Es braucht Node 24 (siehe `.node-version`):
```bash
cd frontend
npm install
npm run dev      # Entwicklungsserver auf http://localhost:5280/app/, leitet /api an Flask auf Port 5000 weiter
npm test         # Tests (Vitest, Testing Library, MSW)
npm run build    # baut nach frontend/dist; Flask liefert das dann unter http://localhost:5000/app/ aus
```

**6. (Optional) MCP-Server mit Claude Desktop verbinden**

Die komplette Anleitung dazu findet sich in [`mcp_server/`](./mcp_server) — kurz zusammengefasst: einen Eintrag in der `claude_desktop_config.json` anlegen, der auf `mcp_server/server.py` verweist und den Python-Interpreter der eigenen virtuellen Umgebung nutzt, danach Claude Desktop neu starten.

## Deployment

Die App läuft live auf [Render](https://render.com):
- **Build-Befehl** `pip install -r requirements.txt && npm ci --prefix frontend && npm run build --prefix frontend` — baut neben den Python-Abhängigkeiten auch das neue Frontend nach `frontend/dist` (Node-Version aus `.node-version`)
- **Web Service** mit dem Startbefehl `python -m flask --app "fintrack:create_app()" upgrade-db && gunicorn app:app --workers=1` — erst werden ausstehende Datenbank-Migrationen ausgeführt, dann startet der Server (ein einzelner Worker ist nötig, damit der Preis-Update-Scheduler nicht mehrfach parallel läuft)
- **PostgreSQL**-Datenbank bei [Neon](https://neon.tech) (kostenloser Tarif, läuft im Gegensatz zur kostenlosen Render-Datenbank nicht ab), verbunden über die Umgebungsvariable `DATABASE_URL`
- Umgebungsvariablen (`OPENAI_API_KEY`, `COINGECKO_API_KEY`, `TAVILY_API_KEY`, `DATABASE_URL`) direkt im Render-Dashboard hinterlegt, nie im Repository gespeichert
- Täglicher Lauf über GitHub Actions ([`daily-jobs.yml`](./.github/workflows/daily-jobs.yml), 21:30 UTC): weckt den schlafenden Server auf, startet `/api/v1/admin/run-daily-jobs` und wartet auf das Ergebnis. Braucht das Repository-Secret `ADMIN_API_KEY` (derselbe Wert wie bei Render). Läuft der Server ohnehin, startet zusätzlich der eingebaute Scheduler um 22:30 Uhr deutscher Zeit — eine Sperre verhindert doppelte Läufe
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
- Trennung von Verantwortlichkeiten über mehrere Module hinweg (Routen, Modelle, Services, Scheduler, Tools, Budget-Logik) sowie Aufteilung von Frontend-CSS/JS pro Seite zur besseren Wartbarkeit
