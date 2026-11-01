"""
contracts/detect.py - Verträge in importierten Kontoumsätzen erkennen.

Kommt dieselbe Abbuchung regelmäßig (monatlich, vierteljährlich, halbjährlich
oder jährlich) mit ähnlichem Betrag, ist das sehr wahrscheinlich ein Vertrag.
Die Vorschläge werden nur berechnet, nie gespeichert; angelegt wird ein Vertrag
erst, wenn der Nutzer ihn bestätigt.
"""

from collections import defaultdict
from statistics import median

from fintrack.imports.bank_service import words
from fintrack.models import Category, Contract, Transaction

# Abstand zwischen zwei Abbuchungen in Tagen -> Zahlweise, dazu wie oft sie mindestens vorkommen muss
INTERVALS = [
    ('monthly', 25, 35, 3),
    ('quarterly', 80, 100, 2),
    ('half_yearly', 170, 195, 2),
    ('yearly', 350, 380, 2),
]
# Beträge dürfen um so viel schwanken (z.B. Strom-Abschlag angepasst)
AMOUNT_SPREAD = 0.15

# Wörter in der Kategorie -> Art des Vertrags (wie die Standardkategorien des Haushaltsbuchs)
KIND_WORDS = [
    ('insurance', ('versicherung', 'haftpflicht', 'kfz')),
    ('energy', ('strom', 'gas', 'nebenkosten', 'energie')),
    ('telecom', ('handy', 'internet', 'telefon', 'mobilfunk')),
    ('subscription', ('streaming', 'abo')),
    ('fitness', ('fitness', 'sport')),
    ('loan', ('kredit', 'leasing', 'darlehen')),
]


def _norm(text):
    return ' '.join((text or '').lower().split())


def _interval(dates):
    gaps = [(b - a).days for a, b in zip(dates, dates[1:])]
    if not gaps:
        return None
    gap = median(gaps)
    for name, low, high, minimum in INTERVALS:
        if low <= gap <= high and len(dates) >= minimum:
            return name
    return None


def _kind(*texts):
    text = ' '.join(t or '' for t in texts).lower()
    for kind, hints in KIND_WORDS:
        if any(hint in text for hint in hints):
            return kind
    return 'other'


def contract_suggestions(user_id):
    """
    Wiederkehrende Ausgaben aus importierten Umsätzen, für die es noch keinen
    Vertrag gibt. Ein Vorschlag nennt Name, letzten Betrag, Zahlweise, erste und
    letzte Abbuchung sowie die vermutete Art des Vertrags.
    """
    categories = {c.id: c for c in Category.query.filter_by(user_id=user_id).all()}
    groups = defaultdict(list)
    for booking in Transaction.query.filter(Transaction.user_id == user_id, Transaction.import_hash.isnot(None),
                                            Transaction.is_recurring.is_(False)).all():
        category = categories.get(booking.category_id)
        if category is not None and category.type != 'income':
            groups[_norm(booking.description)].append(booking)

    # Was schon ein Vertrag ist (über Name oder verknüpfte Buchung), wird nicht noch einmal vorgeschlagen
    contracts = Contract.query.filter_by(user_id=user_id).all()
    known_words = [words(c.name) | words(c.provider) for c in contracts]

    result = []
    for key, bookings in groups.items():
        bookings.sort(key=lambda b: b.date)
        dates = [b.date.date() for b in bookings]
        interval = _interval(dates)
        if interval is None:
            continue
        amounts = [b.amount for b in bookings]
        if max(amounts) - min(amounts) > median(amounts) * AMOUNT_SPREAD:
            continue
        name_words = words(bookings[-1].description)
        if any(name_words and name_words <= known for known in known_words):
            continue
        category = categories[bookings[-1].category_id]
        parent = categories.get(category.parent_id)
        result.append({
            "key": key,
            "name": bookings[-1].description,
            "amount": round(bookings[-1].amount, 2),
            "interval": interval,
            "first_date": dates[0].isoformat(),
            "last_date": dates[-1].isoformat(),
            "count": len(bookings),
            "category_id": category.id,
            "category_name": category.name,
            "kind": _kind(category.name, parent.name if parent else '', bookings[-1].description),
        })
    result.sort(key=lambda s: -s['amount'])
    return result
