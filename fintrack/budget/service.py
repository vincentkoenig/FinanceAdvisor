"""
budget_logic.py - Gemeinsame Berechnungslogik für das Haushaltsbuch.
Wird sowohl von app.py (Web-Endpoint) als auch vom MCP-Server
genutzt, damit die Berechnung nur an einer Stelle existiert.
"""

from bisect import bisect_right
from calendar import monthrange
from datetime import date, datetime, timedelta

from fintrack.models import db, AccountBalance, Transaction, Category
from fintrack.portfolio.history import portfolio_value_series


def is_income(transaction):
    """Prüft ob eine Transaktion eine Einnahme ist, über ihre Kategorie"""
    category = db.session.get(Category, transaction.category_id)
    return category is not None and category.type == 'income'


def runs_in_month(transaction, month_start, month_end):
    """Zählt eine wiederkehrende Buchung in diesem Monat (begonnen, nicht beendet, nicht pausiert)?"""
    starts_before_month_end = transaction.date < month_end
    no_end_or_ends_after_month_start = transaction.end_date is None or transaction.end_date >= month_start

    not_paused_this_month = not transaction.is_paused or (
            transaction.paused_at is not None and transaction.paused_at >= month_end
    )

    return starts_before_month_end and no_end_or_ends_after_month_start and not_paused_this_month


def cash_movements(user_id, today):
    """
    Alle Geldbewegungen bis heute als sortierte Liste (Tag, Betrag mit Vorzeichen).
    Wiederkehrende Buchungen liegen in jedem Monat, in dem sie laufen, auf ihrem
    Tag (am 31. gestartet: im Februar am Monatsletzten) und zählen erst ab diesem Tag.
    """
    types = {c.id: c.type for c in Category.query.filter_by(user_id=user_id).all()}
    movements = []
    for transaction in Transaction.query.filter_by(user_id=user_id).all():
        signed = transaction.amount if types.get(transaction.category_id) == 'income' else -transaction.amount
        if not transaction.is_recurring:
            if transaction.date.date() <= today:
                movements.append((transaction.date.date(), signed))
            continue

        year, month = transaction.date.year, transaction.date.month
        while (year, month) <= (today.year, today.month):
            next_year, next_month = (year + 1, 1) if month == 12 else (year, month + 1)
            if runs_in_month(transaction, datetime(year, month, 1), datetime(next_year, next_month, 1)):
                day = date(year, month, min(transaction.date.day, monthrange(year, month)[1]))
                if day <= today:
                    movements.append((day, signed))
            year, month = next_year, next_month
    return sorted(movements, key=lambda movement: movement[0])


class CashLedger:
    """
    Cash-Bestand aus den eingetragenen Kontoständen und den Buchungen. Ein Kontostand gilt zum
    Ende seines Tages. Von dort rechnen die Buchungen bis zum nächsten Eintrag weiter, vor dem
    ersten Eintrag rückwärts. Ohne Eintrag ist der Bestand unbekannt.
    """

    def __init__(self, user_id, today=None):
        self.today = today or date.today()
        self.balances = AccountBalance.query.filter_by(user_id=user_id).order_by(AccountBalance.date).all()
        self.balance_days = [balance.date for balance in self.balances]
        movements = cash_movements(user_id, self.today)
        self.movement_days = [day for day, _ in movements]
        self.running_total = [0.0]
        for _, amount in movements:
            self.running_total.append(self.running_total[-1] + amount)

    def _total_until(self, day):
        return self.running_total[bisect_right(self.movement_days, day)]

    def _flow(self, after, until):
        """Summe der Bewegungen nach dem Tag after bis einschließlich until."""
        return self._total_until(until) - self._total_until(after)

    def on(self, day):
        """Bestand am Ende des Tages, None ohne eingetragenen Kontostand."""
        if not self.balances:
            return None
        index = bisect_right(self.balance_days, day) - 1
        if index < 0:
            first = self.balances[0]
            return round(first.amount - self._flow(day, first.date), 2)
        return round(self.balances[index].amount + self._flow(self.balances[index].date, day), 2)

    def entries(self):
        """
        Kontostände, neueste zuerst. expected ist, was die Buchungen seit dem Eintrag davor
        erwarten ließen; difference zeigt also, wie viel im Haushaltsbuch dazwischen nicht stimmt.
        """
        result = []
        previous = None
        for balance in self.balances:
            expected = None if previous is None else round(previous.amount + self._flow(previous.date, balance.date), 2)
            result.append({
                "id": balance.id, "date": balance.date.isoformat(), "amount": balance.amount, "expected": expected,
                "difference": None if expected is None else round(balance.amount - expected, 2),
            })
            previous = balance
        return result[::-1]

    def first_day(self):
        return min(self.balance_days[:1] + self.movement_days[:1], default=None)


def wealth_series(user_id, today=None):
    """
    Gesamtvermögen je Tag als Liste von {date, cash, depot, total}, von der ersten Buchung oder dem
    ersten Kontostand bis heute. Ohne eingetragenen Kontostand gibt es keinen Verlauf.
    """
    ledger = CashLedger(user_id, today)
    if not ledger.balances:
        return []

    depot = dict(portfolio_value_series(user_id, ledger.today))
    series = []
    last_depot = 0.0
    day = ledger.first_day()
    while day <= ledger.today:
        last_depot = depot.get(day, last_depot)
        cash = ledger.on(day)
        series.append({"date": day.isoformat(), "cash": cash, "depot": last_depot, "total": round(cash + last_depot, 2)})
        day += timedelta(days=1)
    return series


def calculate_budget_summary(user_id):
    """
    Berechnet den kumulierten Cash-Saldo über alle Monate seit der
    ersten Buchung des Nutzers, sowie eine detaillierte Aufschlüsselung
    des aktuellen Monats (Einnahmen, Fixkosten, Variable Ausgaben, Saldo).
    Wiederkehrende Buchungen werden für jeden Monat mitgezählt,
    in dem sie aktiv waren.
    Gibt ein Dictionary zurück, unabhängig von Flask/jsonify - kann
    also sowohl im Web-Endpoint als auch im MCP-Server genutzt werden.

    cumulative_balance ist nur die Summe der Buchungen und kein Kontostand. Der echte Bestand
    steht in cash_balance (None, solange kein Kontostand eingetragen ist), cash_as_of nennt den
    neuesten Kontostand und last_booking die letzte einmalige Buchung, also bis wohin Umsätze da sind.
    """
    ledger = CashLedger(user_id)
    last_booking = Transaction.query.filter(
        Transaction.user_id == user_id, Transaction.is_recurring.is_(False),
        Transaction.date < datetime.combine(ledger.today + timedelta(days=1), datetime.min.time()),
    ).order_by(Transaction.date.desc()).first()
    cash = {
        "cash_balance": ledger.on(ledger.today),
        "cash_as_of": ledger.balance_days[-1].isoformat() if ledger.balances else None,
        "last_booking": last_booking.date.date().isoformat() if last_booking else None,
    }

    first_transaction = Transaction.query.filter_by(user_id=user_id) \
        .order_by(Transaction.date.asc()).first()

    if not first_transaction:
        return {
            "cumulative_balance": 0,
            "current_month_balance": 0,
            "current_month_income": 0,
            "current_month_fixed": 0,
            "current_month_variable": 0,
            **cash,
        }

    one_time_transactions = Transaction.query.filter_by(user_id=user_id, is_recurring=False).all()
    recurring_transactions = Transaction.query.filter_by(user_id=user_id, is_recurring=True).all()

    cumulative_balance = 0
    current_month_balance = 0
    current_month_income = 0
    current_month_fixed = 0
    current_month_variable = 0

    today = datetime.now()
    current_month_start = datetime(today.year, today.month, 1)

    year = first_transaction.date.year
    month = first_transaction.date.month

    while datetime(year, month, 1) <= today:
        month_start = datetime(year, month, 1)
        month_end = datetime(year + 1, 1, 1) if month == 12 else datetime(year, month + 1, 1)

        month_total = 0
        is_current_month = (month_start == current_month_start)

        all_relevant_transactions = []

        for transaction in one_time_transactions:
            if month_start <= transaction.date < month_end:
                all_relevant_transactions.append(transaction)

        for transaction in recurring_transactions:
            if runs_in_month(transaction, month_start, month_end):
                all_relevant_transactions.append(transaction)

        for transaction in all_relevant_transactions:
            category = db.session.get(Category, transaction.category_id)
            if category and category.is_transfer:
                continue
            category_type = category.type if category else None
            sign = 1 if category_type == 'income' else -1
            month_total += sign * transaction.amount

            # Nur für den aktuellen Monat die Aufschlüsselung nach Typ befüllen
            if is_current_month:
                if category_type == 'income':
                    current_month_income += transaction.amount
                elif category_type == 'fixed_expense':
                    current_month_fixed += transaction.amount
                elif category_type == 'variable_expense':
                    current_month_variable += transaction.amount

        cumulative_balance += month_total

        if is_current_month:
            current_month_balance = month_total

        if month == 12:
            year += 1
            month = 1
        else:
            month += 1

    return {
        "cumulative_balance": round(cumulative_balance, 2),
        "current_month_balance": round(current_month_balance, 2),
        "current_month_income": round(current_month_income, 2),
        "current_month_fixed": round(current_month_fixed, 2),
        "current_month_variable": round(current_month_variable, 2),
        **cash,
    }

def ensure_transfer_categories(user_id):
    """Legt die Kategorien "Umbuchungen" für Eingänge und Abgänge an, falls sie fehlen."""
    for category_type in ('income', 'variable_expense'):
        exists = Category.query.filter_by(user_id=user_id, type=category_type, is_transfer=True, parent_id=None).count()
        if not exists:
            db.session.add(Category(user_id=user_id, name='Umbuchungen', type=category_type, is_transfer=True))


def create_default_categories(user_id):
    """
    Legt für einen neuen Nutzer die Standardkategorien fürs Haushaltsbuch an.
    Struktur: Einkommen, Fixkosten, Variable Ausgaben - jeweils mit
    Hauptkategorien und passenden Unterkategorien.
    Der Nutzer kann diese später beliebig anpassen oder löschen.
    """
    categories = {
        "income": {
            "Einkommen": ["Gehalt", "Kindergeld", "Arbeitslosengeld", "Dividenden", "Sonstige Einnahmen"]
        },
        "fixed_expense": {
            "Wohnen": ["Miete", "Strom", "Nebenkosten"],
            "Versicherungen": ["Haftpflicht", "KFZ", "Sonstige Versicherungen"],
            "Investments": ["Sparplan", "Sonstige Investments"],
            "Mobilität": ["Auto/Leasing", "ÖPNV-Abo"],
            "Sonstige Verträge": ["Handy/Internet", "Streaming/Abos"]
        },
        "variable_expense": {
            "Lebenshaltung": ["Lebensmittel", "Kleidung", "Drogerie"],
            "Mobilität": ["Sprit", "Taxi/Fahrdienst"],
            "Entertainment & Interessen": ["Kino", "Hobbys"],
            "Sonstiges": ["Geschenke", "Spenden"]
        }
    }

    for category_type, main_categories in categories.items():
        for main_name, sub_names in main_categories.items():
            # Hauptkategorie anlegen
            main_category = Category(user_id=user_id, name=main_name, type=category_type)
            db.session.add(main_category)
            db.session.flush()  # damit main_category.id sofort verfügbar ist

            # Unterkategorien anlegen, verweisen auf die Hauptkategorie
            for sub_name in sub_names:
                sub_category = Category(
                    user_id=user_id,
                    name=sub_name,
                    type=category_type,
                    parent_id=main_category.id
                )
                db.session.add(sub_category)

    ensure_transfer_categories(user_id)
    db.session.commit()
