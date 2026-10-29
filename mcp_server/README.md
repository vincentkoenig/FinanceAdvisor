# FinTrack MCP Server

Ein eigenständiger [Model Context Protocol](https://modelcontextprotocol.io)-Server, der Portfolio- und Haushaltsbuch-Daten aus FinTrack für MCP-fähige Clients wie Claude Desktop bereitstellt.

Der Server nutzt dieselbe App, dieselben Modelle und dieselbe Berechnungslogik (`fintrack/budget/service.py`) wie die Web-App, sodass keine Geschäftslogik doppelt gepflegt werden muss. Er greift auf genau ein Konto zu, festgelegt über `FINTRACK_USER_EMAIL`.

## Verfügbare Tools

### `get_portfolio_summary`
Gibt eine Zusammenfassung des aktuellen Portfolios zurück — alle gehaltenen Assets mit Menge und durchschnittlichem Kaufpreis.

### `get_budget_status`
Gibt eine Übersicht über den aktuellen Haushaltsbuch-Status zurück: Einnahmen, Fixkosten und variable Ausgaben des laufenden Monats, den Saldo des Monats, sowie den kumulierten Cash-Bestand seit der ersten Buchung.

### `add_transaction`
Legt eine neue, einmalige Buchung im Haushaltsbuch an. Nimmt einen Kategorienamen (z.B. `"Lebensmittel"`), einen Betrag, sowie optional eine Beschreibung und ein Datum entgegen. Der Kategorienname wird case-insensitiv gegen die vorhandenen Unterkategorien des Nutzers abgeglichen; ist keine passende Kategorie vorhanden, gibt das Tool eine Liste der verfügbaren Kategorien zurück. Für wiederkehrende Buchungen ist weiterhin das Web-Frontend zu nutzen.

## Voraussetzungen

- Python-Umgebung des Hauptprojekts (`../.venv`), inklusive der Abhängigkeiten aus `requirements.txt` in diesem Ordner (enthält die der Web-App plus das MCP-SDK)
- Ein FinTrack-Konto in der Datenbank, auf die der Server zugreifen soll
- [Claude Desktop](https://claude.ai/download) als MCP-Client

Installiere die für den MCP-Server benötigten Abhängigkeiten:

```bash
pip install -r requirements.txt
```

## Einrichtung mit Claude Desktop

Der Server läuft lokal über stdio und wird von Claude Desktop über eine Konfigurationsdatei gestartet. Diese Datei liegt je nach Installationsart unter einem der folgenden Pfade:

- `%APPDATA%\Claude\claude_desktop_config.json`
- `%APPDATA%\Local\Packages\Claude_<id>\LocalCache\Roaming\Claude\claude_desktop_config.json` (bei Installation über den Microsoft Store)

Ergänze dort einen Eintrag unter `mcpServers`, ohne bestehende Einträge zu entfernen:

```json
{
  "mcpServers": {
    "financeadvisor": {
      "command": "C:\\Pfad\\zu\\FinanceAdvisor\\.venv\\Scripts\\python.exe",
      "args": [
        "C:\\Pfad\\zu\\FinanceAdvisor\\mcp_server\\server.py"
      ],
      "env": {
        "FINTRACK_USER_EMAIL": "deine@email.de"
      }
    }
  }
}
```

| Variable | Zweck |
|---|---|
| `FINTRACK_USER_EMAIL` | **Pflicht.** E-Mail des FinTrack-Kontos, auf das der Server zugreift. Fehlt sie, antworten die Tools mit einem Hinweis statt mit Daten. |
| `DATABASE_URL` | Optional. Ohne Angabe nutzt der Server die lokale SQLite-Datei `instance/finance_advisor.db`. Um mit deinen echten Daten zu arbeiten, hier den Neon-Connection-String eintragen — **nur** in der Claude-Desktop-Konfiguration, nicht in der `.env`, damit die lokale Entwicklung weiter gegen SQLite läuft. |

Wichtig: `command` muss auf den Python-Interpreter der **virtuellen Umgebung** des Hauptprojekts zeigen, nicht auf eine globale Python-Installation, da dort die benötigten Pakete (`mcp`, `flask`, `flask-sqlalchemy`) installiert sind.

Nach dem Speichern Claude Desktop vollständig beenden und neu starten. Der Server `financeadvisor` sollte danach im Bereich für Connectors/MCP-Server als verbunden angezeigt werden.

## Manuell starten

Zum Testen außerhalb von Claude Desktop lässt sich der Server auch direkt aus dem Projekt-Hauptordner heraus starten:

```bash
python mcp_server/server.py
```

Der Server wartet dann über stdio auf Verbindungen von einem MCP-Client.

## Sicherheit

Der Server hat kein eigenes Login: Wer ihn starten kann, kann über ihn auf das Konto aus `FINTRACK_USER_EMAIL` zugreifen. Er läuft deshalb nur lokal über stdio und ist nicht aus dem Netz erreichbar. Steht in `DATABASE_URL` die Produktionsdatenbank, liegt dieser Zugang in der Claude-Desktop-Konfiguration auf deinem Rechner — die Datei entsprechend schützen.