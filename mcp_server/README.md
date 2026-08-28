# FinTrack MCP Server

Ein eigenständiger [Model Context Protocol](https://modelcontextprotocol.io)-Server, der Portfolio- und Haushaltsbuch-Daten aus FinTrack für MCP-fähige Clients wie Claude Desktop bereitstellt.

Der Server greift direkt auf dieselbe SQLite-Datenbank zu wie die Web-App und nutzt dieselbe Berechnungslogik (`budget_logic.py`), sodass keine Geschäftslogik doppelt gepflegt werden muss.

## Verfügbare Tools

### `get_portfolio_summary`
Gibt eine Zusammenfassung des aktuellen Portfolios zurück — alle gehaltenen Assets mit Menge und durchschnittlichem Kaufpreis.

### `get_budget_status`
Gibt eine Übersicht über den aktuellen Haushaltsbuch-Status zurück: Einnahmen, Fixkosten und variable Ausgaben des laufenden Monats, den Saldo des Monats, sowie den kumulierten Cash-Bestand seit der ersten Buchung.

### `add_transaction`
Legt eine neue, einmalige Buchung im Haushaltsbuch an. Nimmt einen Kategorienamen (z.B. `"Lebensmittel"`), einen Betrag, sowie optional eine Beschreibung und ein Datum entgegen. Der Kategorienname wird case-insensitiv gegen die vorhandenen Unterkategorien des Nutzers abgeglichen; ist keine passende Kategorie vorhanden, gibt das Tool eine Liste der verfügbaren Kategorien zurück. Für wiederkehrende Buchungen ist weiterhin das Web-Frontend zu nutzen.

## Voraussetzungen

- Python-Umgebung des Hauptprojekts (`../.venv`), inklusive der Abhängigkeiten aus `requirements.txt` in diesem Ordner
- Eine bereits initialisierte FinTrack-Datenbank (`../instance/finance_advisor.db`)
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
      ]
    }
  }
}
```

Wichtig: `command` muss auf den Python-Interpreter der **virtuellen Umgebung** des Hauptprojekts zeigen, nicht auf eine globale Python-Installation, da dort die benötigten Pakete (`mcp`, `flask`, `flask-sqlalchemy`) installiert sind.

Nach dem Speichern Claude Desktop vollständig beenden und neu starten. Der Server `financeadvisor` sollte danach im Bereich für Connectors/MCP-Server als verbunden angezeigt werden.

## Manuell starten

Zum Testen außerhalb von Claude Desktop lässt sich der Server auch direkt aus dem Projekt-Hauptordner heraus starten:

```bash
python mcp_server/server.py
```

Der Server wartet dann über stdio auf Verbindungen von einem MCP-Client.

## Feste Nutzer-ID

Der Server läuft standalone ohne eigenes Login-System und arbeitet daher mit einer festen `DEFAULT_USER_ID` in `server.py`. Für Mehrnutzer-Betrieb müsste diese durch einen Parameter oder eine Authentifizierung ersetzt werden.