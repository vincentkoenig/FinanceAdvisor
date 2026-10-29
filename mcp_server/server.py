"""
server.py - MCP-Server, der FinTrack-Daten für MCP-fähige Clients wie
Claude Desktop bereitstellt (Portfolio, Haushaltsbuch, neue Buchungen).

Läuft lokal über stdio und nutzt dieselbe App, dieselben Modelle und
dieselbe Berechnungslogik wie die Web-App. Konfiguration über
Umgebungsvariablen (z.B. im "env"-Block der Claude-Desktop-Konfiguration):

- FINTRACK_USER_EMAIL  E-Mail des Kontos, auf das der Server zugreift (Pflicht)
- DATABASE_URL         optional: Datenbank, z.B. die Neon-Datenbank.
                       Ohne Angabe die lokale SQLite-Datei instance/finance_advisor.db
"""

import os
import sys
from datetime import datetime

# Projekt-Root in den Suchpfad - Claude Desktop startet den Server aus
# einem beliebigen Arbeitsverzeichnis (z.B. C:\Windows\system32)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from mcp.server.mcpserver import MCPServer

from fintrack import create_app
from fintrack.auth.routes import find_user_by_email
from fintrack.budget.service import calculate_budget_summary
from fintrack.extensions import db
from fintrack.models import Asset, Category, Transaction, UserAsset

# Gleiche App wie die Web-App, aber ohne Scheduler (den startet nur app.py)
app = create_app()

mcp = MCPServer("FinTrack")


class UserNotConfigured(Exception):
    """FINTRACK_USER_EMAIL fehlt oder passt zu keinem Konto."""


def current_user():
    """
    Das Konto, auf das der Server zugreift - festgelegt über
    FINTRACK_USER_EMAIL statt einer fest eingebauten User-ID.
    Muss innerhalb eines App-Kontexts aufgerufen werden.
    """
    email = os.getenv('FINTRACK_USER_EMAIL')
    if not email:
        raise UserNotConfigured(
            'FINTRACK_USER_EMAIL ist nicht gesetzt. Trage die E-Mail deines '
            'FinTrack-Kontos im "env"-Block der MCP-Konfiguration ein.')
    user = find_user_by_email(email)
    if not user:
        raise UserNotConfigured(f'Kein FinTrack-Konto für {email} gefunden.')
    return user


@mcp.tool()
def hello_portfolio() -> str:
    """Gibt eine Testnachricht zurück, um die Verbindung zu prüfen."""
    return "Verbindung zum FinTrack MCP-Server steht!"


@mcp.tool()
def get_portfolio_summary() -> str:
    """
    Gibt eine Zusammenfassung des Portfolios zurück -
    alle aktuell gehaltenen Assets mit Menge und Kaufpreis.
    """
    with app.app_context():
        try:
            user = current_user()
        except UserNotConfigured as error:
            return str(error)

        holdings = UserAsset.query.filter_by(user_id=user.id) \
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
    with app.app_context():
        try:
            user = current_user()
        except UserNotConfigured as error:
            return str(error)

        summary = calculate_budget_summary(user.id)

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
    with app.app_context():
        try:
            user = current_user()
        except UserNotConfigured as error:
            return str(error)

        # Kategorie anhand des Namens suchen - Groß-/Kleinschreibung
        # wird dabei ignoriert, damit "lebensmittel" auch "Lebensmittel" trifft
        category = Category.query.filter_by(user_id=user.id) \
            .filter(db.func.lower(Category.name) == category_name.lower()) \
            .first()

        if not category:
            # Verfügbare Kategorien auflisten, damit Claude einen
            # passenden Vorschlag machen kann, statt einfach zu scheitern
            available = Category.query.filter_by(user_id=user.id).all()
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
            user_id=user.id,
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
