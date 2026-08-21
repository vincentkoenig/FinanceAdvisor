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
from models import db, User, Asset, UserAsset, Category, Transaction
from budget_logic import calculate_budget_summary
from datetime import datetime

# Absoluter Pfad zur Datenbank-Datei, damit es unabhängig vom
# Arbeitsverzeichnis funktioniert
DB_PATH = os.path.join(PROJECT_ROOT, 'instance', 'finance_advisor.db')

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


@mcp.tool()
def get_budget_status() -> str:
    """
    Gibt eine Übersicht über den aktuellen Haushaltsbuch-Status zurück -
    Einnahmen, Fixkosten, Variable Ausgaben und Saldo des laufenden
    Monats, sowie den kumulierten Cash-Bestand seit Beginn der Buchungen.
    Nutzt dieselbe Berechnungslogik wie die Budget-Seite der Web-App.
    """
    with db_app.app_context():
        summary = calculate_budget_summary(DEFAULT_USER_ID)

        return (
            f"Haushaltsbuch-Status für den aktuellen Monat:\n"
            f"- Einnahmen: {summary['current_month_income']} €\n"
            f"- Fixkosten: {summary['current_month_fixed']} €\n"
            f"- Variable Ausgaben: {summary['current_month_variable']} €\n"
            f"- Saldo diesen Monat: {summary['current_month_balance']} €\n\n"
            f"Kumulierter Cash-Bestand seit Beginn: {summary['cumulative_balance']} €"
        )


@mcp.tool()
def add_transaction(category_name: str, amount: float, description: str = "", date: str = "") -> str:
    """
    Legt eine neue, einmalige Buchung (Einnahme oder Ausgabe) im
    Haushaltsbuch an. category_name wird gegen die vorhandenen
    Kategorien des Nutzers abgeglichen (z.B. "Lebensmittel", "Gehalt").
    date im Format YYYY-MM-DD, wird bei leerem Wert auf heute gesetzt.
    Für wiederkehrende Buchungen bitte das Web-Frontend nutzen.
    """
    with db_app.app_context():
        # Kategorie anhand des Namens suchen - Groß-/Kleinschreibung
        # wird dabei ignoriert, damit "lebensmittel" auch "Lebensmittel" trifft
        category = Category.query.filter_by(user_id=DEFAULT_USER_ID) \
            .filter(db.func.lower(Category.name) == category_name.lower()) \
            .first()

        if not category:
            # Verfügbare Kategorien auflisten, damit Claude einen
            # passenden Vorschlag machen kann, statt einfach zu scheitern
            available = Category.query.filter_by(user_id=DEFAULT_USER_ID).all()
            names = ", ".join(c.name for c in available)
            return (
                f"Keine Kategorie namens '{category_name}' gefunden. "
                f"Verfügbare Kategorien: {names}"
            )

        # Nur Unterkategorien dürfen Buchungen bekommen, keine
        # Hauptkategorien (parent_id ist dann None) - analog zum Frontend
        if category.parent_id is None:
            return (
                f"'{category_name}' ist eine Hauptkategorie, keine Unterkategorie. "
                f"Bitte eine konkrete Unterkategorie angeben, z.B. 'Lebensmittel' statt 'Lebenshaltung'."
            )

        if amount <= 0:
            return "Der Betrag muss größer als 0 sein."

        # Datum parsen, bei leerem Wert oder Fehler heutiges Datum nutzen
        if date:
            try:
                transaction_date = datetime.strptime(date, '%Y-%m-%d')
            except ValueError:
                return f"Ungültiges Datumsformat '{date}'. Bitte YYYY-MM-DD verwenden, z.B. 2026-08-20."
        else:
            transaction_date = datetime.now()

        new_transaction = Transaction(
            user_id=DEFAULT_USER_ID,
            category_id=category.id,
            amount=amount,
            description=description if description else None,
            date=transaction_date,
            is_recurring=False
        )
        db.session.add(new_transaction)
        db.session.commit()

        type_label = "Einnahme" if category.type == "income" else "Ausgabe"
        return (
            f"{type_label} erfolgreich eingetragen: {amount} € "
            f"unter '{category.name}' am {transaction_date.strftime('%d.%m.%Y')}."
        )

if __name__ == "__main__":
    mcp.run()