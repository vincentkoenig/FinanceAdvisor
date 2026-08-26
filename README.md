# FinTrack (ehemals FinanceAdvisor) 💹

Eine KI-gestützte Finanz-Web-App auf Basis von **Flask** und **OpenAI**. Verwalte dein Investment-Portfolio, führe ein Haushaltsbuch, chatte mit einem KI-Finanzberater und lass dir strukturierte Portfolio-Analysen erstellen — installierbar als mobile App (PWA), live deployed auf Render, und über einen eigenen MCP-Server auch für Claude Desktop nutzbar.

**Live-Demo:** https://financeadvisor-snxz.onrender.com *(kostenloser Tarif — nach Inaktivität kann der erste Aufruf 30-60 Sekunden dauern, während der Server aufwacht)*

## Features

### 🏠 Home-Übersicht
- Zentrales Dashboard mit Portfolio-Wert, kumuliertem Cash-Bestand und Gesamtvermögen
- Kombiniert die live bewertete Portfolio-Position mit dem laufenden Saldo aus dem Haushaltsbuch

### 📊 Portfolio & Watchlist
- Aktien, ETFs, Kryptowährungen und Edelmetalle hinzufügen, kaufen und verkaufen
- Assets können per Name (z.B. „Tesla") hinzugefügt werden — das passende Symbol wird automatisch über **yfinance** aufgelöst
- Live-Preise werden bei jedem Seitenaufruf über **yfinance** und die **CoinGecko API** abgerufen
- Automatische Neuberechnung des durchschnittlichen Kaufpreises bei weiteren Käufen
- Historische Preise werden beim Hinzufügen eines neuen Assets automatisch für 1 Jahr geladen, zusätzlich sorgt ein Hintergrund-Scheduler (**APScheduler**) für tägliche Preis-Snapshots inklusive Lückenfüllung für eine durchgehende Chart-Historie
- Interaktiver Portfolio-Wert-Chart mit wählbaren Zeiträumen (1W / 1M / YTD / 1J / Max), mit vorwärts aufgefüllten Preisen, damit Wochenenden/Feiertage und neu hinzugefügte Assets den Chart nicht verzerren
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
- Registrierung und Login mit E-Mail und gehashtem Passwort (`werkzeug.security`)
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
- **APScheduler** — Hintergrund-Scheduler für tägliche Preis-Snapshots und Lückenfüllung
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
├── app.py                    # Alle Flask-Routen
├── models.py                  # SQLAlchemy-Modelle + Pydantic-Schemas für Structured Output
├── budget_logic.py             # Gemeinsame Haushaltsbuch-Berechnungslogik (genutzt von app.py und mcp_server)
├── api_services.py             # Live-Preisabruf (Aktien, Krypto, Edelmetalle, Wechselkurs, Websuche)
├── scheduler.py                 # APScheduler — tägliche Preis-Snapshots mit Lückenfüllung
├── tools.py                     # OpenAI Function-Calling-Tool-Definitionen
├── requirements.txt              # Abhängigkeiten der Haupt-App (Flask, gunicorn, psycopg2-binary, etc.)
├── start.bat                     # Windows-Starter — startet den Server und öffnet den Browser
├── mcp_server/
│   ├── server.py                  # MCP-Server, stellt Portfolio-/Budget-Tools für Claude Desktop bereit
│   └── requirements.txt            # Separate, schlanke Abhängigkeiten nur für die lokale MCP-Nutzung
├── docs/                          # Screenshots, Demo-Video, sonstige Projekt-Assets
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
│       ├── utils.js                       # Gemeinsame Hilfsfunktionen (z.B. dynamische Farbgenerierung)
│       └── logout.js
└── templates/
    ├── index.html                # Login / Registrierung
    ├── home.html                  # Vermögensübersicht
    ├── portfolio.html              # Portfolio-Übersicht, Chart und Watchlist-Tab
    ├── budget.html                  # Haushaltsbuch
    ├── chat.html                     # Vollbild-Chat-Oberfläche
    ├── analyse.html                   # Portfolio-Analyse & Verlauf
    └── settings.html                   # Nutzerprofil-Einstellungen
```

## API-Übersicht

| Methode | Route | Beschreibung |
|--------|-------|-------------|
| `POST` | `/register` | Neuen Nutzer registrieren (legt automatisch Standard-Budgetkategorien an) |
| `POST` | `/login` | Login |
| `GET` | `/users/<id>` | Nutzerprofil abrufen |
| `PUT` | `/users/<id>/settings` | Anlage-Einstellungen aktualisieren |
| `GET` | `/assets/<id>` | Asset-Details mit Live-Preis abrufen |
| `GET` | `/assets/search` | Asset per Name oder Symbol suchen, legt es bei Bedarf automatisch an und lädt historische Preise |
| `POST` | `/assets/<id>/prices` | Manuell einen historischen Preiseintrag hinzufügen |
| `GET` | `/users/<id>/assets` | Portfolio abrufen (Live-Preise) |
| `POST` | `/users/<id>/assets` | Asset zum Portfolio hinzufügen |
| `PUT` | `/users/<id>/assets/<id>/buy` | Kauf erfassen (aktualisiert den Durchschnittspreis) |
| `PUT` | `/users/<id>/assets/<id>/sell` | Verkauf erfassen |
| `GET` | `/users/<id>/portfolio/history` | Preishistorie für den Chart |
| `POST` | `/portfolio/analyze` | KI-Portfolio-Analyse |
| `GET` | `/users/<id>/portfolio/analyses` | Alle vorherigen Analysen abrufen |
| `POST` | `/chat` | KI-Chat mit Function Calling und Websuche |
| `GET` | `/chat/history/<id>` | Chatverlauf abrufen |
| `GET/POST/DELETE` | `/users/<id>/watchlist` | Watchlist verwalten |
| `POST` | `/update-prices` | Preisaktualisierung manuell anstoßen |
| `GET` | `/users/<id>/categories` | Alle Budgetkategorien eines Nutzers abrufen |
| `POST` | `/users/<id>/categories` | Neue Kategorie oder Unterkategorie hinzufügen |
| `DELETE` | `/categories/<id>` | Kategorie (samt Unterkategorien) löschen |
| `POST` | `/users/<id>/categories/init-defaults` | Standardkategorien nachträglich für einen bestehenden Nutzer anlegen |
| `GET` | `/users/<id>/transactions` | Buchungen abrufen, optional gefiltert nach Monat (`?month=YYYY-MM`) |
| `POST` | `/users/<id>/transactions` | Buchung hinzufügen (einmalig oder wiederkehrend) |
| `DELETE` | `/transactions/<id>` | Buchung löschen |
| `GET` | `/users/<id>/budget/summary` | Kumulierter Cash-Bestand und Aufschlüsselung des aktuellen Monats |

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

**4. App starten**
```bash
python app.py
```
Alternativ unter Windows: Doppelklick auf `start.bat`, um den Server zu starten und automatisch im Browser zu öffnen.

Die SQLite-Datenbank wird beim ersten Start automatisch im `instance/`-Ordner angelegt. Der Preis-Scheduler startet im Hintergrund.

**5. Im Browser öffnen**
```
http://localhost:5000
```
Auf dem Smartphone bietet Chrome an, die App über „Zum Startbildschirm hinzufügen" bzw. den Installations-Prompt als PWA zu installieren.

**6. (Optional) MCP-Server mit Claude Desktop verbinden**

Die komplette Anleitung dazu findet sich in [`mcp_server/`](./mcp_server) — kurz zusammengefasst: einen Eintrag in der `claude_desktop_config.json` anlegen, der auf `mcp_server/server.py` verweist und den Python-Interpreter der eigenen virtuellen Umgebung nutzt, danach Claude Desktop neu starten.

## Deployment

Die App läuft live auf [Render](https://render.com):
- **Web Service** mit `gunicorn app:app --workers=1` (ein einzelner Worker ist nötig, damit der Preis-Update-Scheduler nicht mehrfach parallel läuft)
- **PostgreSQL**-Datenbank (kostenloser Tarif), verbunden über die Umgebungsvariable `DATABASE_URL`
- Umgebungsvariablen (`OPENAI_API_KEY`, `COINGECKO_API_KEY`, `TAVILY_API_KEY`, `DATABASE_URL`) direkt im Render-Dashboard hinterlegt, nie im Repository gespeichert

## Was ich dabei gelernt habe

- Aufbau einer vollständigen, mehrseitigen Flask-REST-API mit über 30 Endpoints
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
