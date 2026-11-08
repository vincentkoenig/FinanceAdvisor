"""
contracts/detect.py - Verträge in importierten Kontoumsätzen erkennen.

Kommt dieselbe Abbuchung regelmäßig (monatlich, vierteljährlich, halbjährlich
oder jährlich) mit ähnlichem Betrag, ist das sehr wahrscheinlich ein Vertrag.
Die Vorschläge werden nur berechnet, nie gespeichert; angelegt wird ein Vertrag
erst, wenn der Nutzer ihn bestätigt. Gespeichert wird nur, welche Vorschläge der
Nutzer ausgeblendet hat (ContractSuggestionDismissal).
"""

from collections import defaultdict
from statistics import median

from fintrack.imports.bank_service import words
from fintrack.models import Category, Contract, ContractSuggestionDismissal, Transaction

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


def _close(a, b):
    """Zwei Beträge liegen so nah beieinander, dass sie zum selben Vertrag gehören können."""
    return abs(a - b) <= max(a, b) * AMOUNT_SPREAD


def _regular(bookings):
    """Zahlweise, wenn die Abbuchungen regelmäßig mit ähnlichem Betrag kommen, sonst None."""
    interval = _interval([b.date.date() for b in bookings])
    amounts = [b.amount for b in bookings]
    if interval is None or max(amounts) - min(amounts) > median(amounts) * AMOUNT_SPREAD:
        return None
    return interval


def _clusters(groups):
    """
    Fasst Empfänger zusammen, die wohl derselbe Vertrag sind: Sie teilen ein
    aussagekräftiges Wort (z.B. "allianz") und buchen einen ähnlichen Betrag ab.
    So wird ein Vertrag, dessen Empfängername sich bei der Bank geändert hat,
    nur einmal vorgeschlagen. Gibt Listen von Schlüsseln aus `groups` zurück.
    """
    keys = list(groups)
    parent = {key: key for key in keys}

    def root(key):
        while parent[key] != key:
            parent[key] = parent[parent[key]]
            key = parent[key]
        return key

    info = {key: (words(groups[key][-1].description), median(b.amount for b in groups[key])) for key in keys}
    for i, a in enumerate(keys):
        for b in keys[i + 1:]:
            (words_a, amount_a), (words_b, amount_b) = info[a], info[b]
            if words_a & words_b and _close(amount_a, amount_b):
                parent[root(b)] = root(a)

    clusters = defaultdict(list)
    for key in keys:
        clusters[root(key)].append(key)
    return list(clusters.values())


def dismissed_keys(user_id):
    return {d.key for d in ContractSuggestionDismissal.query.filter_by(user_id=user_id).all()}


def contract_suggestions(user_id):
    """
    Wiederkehrende Ausgaben aus importierten Umsätzen, für die es noch keinen
    Vertrag gibt. Ein Vorschlag nennt Name, letzten Betrag, Zahlweise, erste und
    letzte Abbuchung sowie die vermutete Art des Vertrags.
    Ein Vorschlag kann mehrere Empfängernamen umfassen (keys, aliases); ausgeblendet
    ist er, sobald einer seiner Schlüssel ausgeblendet wurde.
    """
    categories = {c.id: c for c in Category.query.filter_by(user_id=user_id).all()}
    groups = defaultdict(list)
    for booking in Transaction.query.filter(Transaction.user_id == user_id, Transaction.import_hash.isnot(None),
                                            Transaction.is_recurring.is_(False)).all():
        category = categories.get(booking.category_id)
        if category is not None and category.type != 'income' and not category.is_transfer:
            groups[_norm(booking.description)[:200]].append(booking)
    for bookings in groups.values():
        bookings.sort(key=lambda b: b.date)

    # Was schon ein Vertrag ist (über Name oder verknüpfte Buchung), wird nicht noch einmal vorgeschlagen
    contracts = Contract.query.filter_by(user_id=user_id).all()
    known_words = [words(c.name) | words(c.provider) for c in contracts]
    dismissed = dismissed_keys(user_id)

    candidates = []
    for cluster in _clusters(groups):
        merged = sorted((b for key in cluster for b in groups[key]), key=lambda b: b.date)
        interval = _regular(merged) if len(cluster) > 1 else None
        if interval:
            candidates.append((cluster, merged, interval))
            continue
        # Zusammen nicht regelmäßig (z.B. zwei verschiedene Verträge beim selben Anbieter): einzeln prüfen
        for key in cluster:
            interval = _regular(groups[key])
            if interval:
                candidates.append(([key], groups[key], interval))

    result = []
    for cluster, bookings, interval in candidates:
        if dismissed.intersection(cluster):
            continue
        names = [groups[key][-1].description for key in cluster]
        if any(name_words and name_words <= known for name_words in map(words, names) for known in known_words):
            continue
        latest = bookings[-1]
        # Neuester Empfängername zuerst, die anderen als "auch als"
        cluster = sorted(cluster, key=lambda key: groups[key][-1].date, reverse=True)
        category = categories[latest.category_id]
        parent = categories.get(category.parent_id)
        result.append({
            "key": cluster[0],
            "keys": cluster,
            "name": latest.description,
            "aliases": [groups[key][-1].description for key in cluster[1:]],
            "amount": round(latest.amount, 2),
            "interval": interval,
            "first_date": bookings[0].date.date().isoformat(),
            "last_date": latest.date.date().isoformat(),
            "count": len(bookings),
            "category_id": category.id,
            "category_name": category.name,
            "kind": _kind(category.name, parent.name if parent else '', latest.description),
        })
    result.sort(key=lambda s: -s['amount'])
    return result
