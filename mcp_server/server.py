from mcp.server.mcpserver import MCPServer
import sys
import os

# Absoluten Pfad zum Projekt-Root berechnen - unabhängig davon,
# aus welchem Arbeitsverzeichnis der Server gestartet wird
# (Claude Desktop startet ihn z.B. aus C:\Windows\system32,
# nicht aus dem Projektordner selbst)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from flask import Flask
from models import db, User, Asset, UserAsset

# Absoluter Pfad zur Datenbank-Datei, damit es unabhängig vom
# Arbeitsverzeichnis funktioniert
DB_PATH = os.path.join(PROJECT_ROOT, 'finance_advisor.db')

db_app = Flask(__name__)
db_app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{DB_PATH}'
# instance_path explizit setzen, damit Flask nicht versucht einen
# Ordner relativ zum (unbekannten) Arbeitsverzeichnis anzulegen
db_app.instance_path = os.path.join(PROJECT_ROOT, 'instance')
db.init_app(db_app)

# Feste User-ID für den Start - MCP-Server läuft standalone ohne
# Login/Session, Claude Desktop "meldet sich" nicht als Nutzer an
DEFAULT_USER_ID = 1

mcp = MCPServer("FinanceAdvisor")


@mcp.tool()
def hello_portfolio() -> str:
    """Gibt eine Testnachricht zurück, um die Verbindung zu prüfen."""
    return "Verbindung zum FinanceAdvisor MCP-Server steht!"


@mcp.tool()
def get_portfolio_summary() -> str:
    """
    Gibt eine Zusammenfassung des Portfolios zurück -
    alle aktuell gehaltenen Assets mit Menge und Kaufpreis.
    """
    with db_app.app_context():
        user = db.session.get(User, DEFAULT_USER_ID)

        if not user:
            return f"Kein Nutzer mit ID {DEFAULT_USER_ID} gefunden."

        holdings = UserAsset.query.filter_by(user_id=DEFAULT_USER_ID) \
            .filter(UserAsset.quantity > 0).all()

        if not holdings:
            return f"{user.username} besitzt aktuell keine Assets."

        lines = [f"Portfolio von {user.username}:"]
        for holding in holdings:
            asset = db.session.get(Asset, holding.asset_id)
            lines.append(
                f"- {asset.name} ({asset.symbol}): {holding.quantity} Stück, "
                f"Ø Kaufpreis {holding.avg_buy_price} {asset.currency}"
            )

        return "\n".join(lines)


if __name__ == "__main__":
    mcp.run()