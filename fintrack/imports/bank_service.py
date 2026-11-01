"""
imports/bank_service.py - Gelesene Kontoumsätze gegen das Haushaltsbuch prüfen und übernehmen.

Vorschau (nichts wird gespeichert), je Umsatz:
- 'duplicate': wurde schon einmal importiert (gleicher Fingerabdruck)
- 'covered':   passt zu einer wiederkehrenden Buchung, die in diesem Monat läuft
               (z.B. Miete, Gehalt) - sonst stünde er doppelt im Haushaltsbuch
- 'new':       wird übernommen, mit vorgeschlagener Kategorie, falls eine passt

Übernehmen: nur die bestätigten Umsätze, alles in einer Datenbank-Transaktion.
"""

import hashlib
import re
from collections import Counter
from datetime import datetime

from fintrack.api import ApiError
from fintrack.extensions import db
from fintrack.models import Category, Transaction

# Ein Umsatz gilt als "schon erfasst", wenn er so nah am Betrag der wiederkehrenden Buchung liegt
COVER_TOLERANCE = 0.05
STOP_WORDS = {'gmbh', 'ag', 'se', 'kg', 'und', 'der', 'die', 'das', 'für', 'fuer', 'von', 'sepa', 'lastschrift',
              'gutschrift', 'überweisung', 'ueberweisung', 'dauerauftrag', 'e.v.', 'co', 'europe', 'deutschland'}


def _norm(text):
    return re.sub(r'\s+', ' ', (text or '').lower()).strip()


def words(text):
    """Aussagekräftige Wörter (ohne Rechtsformen und Buchungsarten) für den Textvergleich."""
    return {w for w in re.findall(r'[a-zäöüß0-9]{3,}', _norm(text)) if w not in STOP_WORDS}


def fingerprint(day, amount, counterparty, purpose, occurrence):
    """
    Fingerabdruck eines Umsatzes. occurrence zählt gleiche Umsätze am selben Tag
    (zwei Kaffees zu 3,20 €), damit echte Wiederholungen nicht als Dublette gelten.
    """
    raw = f'{day.isoformat()}|{amount:.2f}|{_norm(counterparty)}|{_norm(purpose)}|{occurrence}'
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()[:40]


def occurrences(rows):
    """Je Umsatz: wie viele gleiche Umsätze davor in der Datei stehen (0, 1, ...)."""
    seen = Counter()
    result = []
    for row in rows:
        key = (row.day, row.amount, _norm(row.counterparty), _norm(row.purpose))
        result.append(seen[key])
        seen[key] += 1
    return result


def description_for(counterparty, purpose):
    """Text der Buchung: Empfänger, sonst Verwendungszweck, gekürzt aufs Feldmaß."""
    return (counterparty or purpose or 'Umsatz')[:200]


def _runs_in_month(booking, day):
    month_start = datetime(day.year, day.month, 1)
    month_end = datetime(day.year + (day.month == 12), day.month % 12 + 1, 1)
    paused = booking.is_paused and (booking.paused_at is None or booking.paused_at < month_end)
    return (booking.date < month_end and (booking.end_date is None or booking.end_date >= month_start)
            and not paused)


def _covering_booking(row, recurring, used):
    """Wiederkehrende Buchung, die diesen Umsatz schon abdeckt (gleiche Richtung, Betrag ±5 %, Monat läuft)."""
    row_words = words(f'{row.counterparty} {row.purpose}')
    for booking, kind in recurring:
        if (kind == 'income') != (row.amount > 0) or (booking.id, row.day.year, row.day.month) in used:
            continue
        if not _runs_in_month(booking, row.day):
            continue
        if abs(abs(row.amount) - booking.amount) > max(1.0, booking.amount * COVER_TOLERANCE):
            continue
        # Gleicher Betrag auf den Cent oder ein gemeinsames Wort (z.B. "Miete", Name des Vermieters)
        if abs(abs(row.amount) - booking.amount) < 0.005 or row_words & words(booking.description):
            used.add((booking.id, row.day.year, row.day.month))
            return booking
    return None


def _suggestions(user_id, categories):
    """Kategorie je Wort aus früheren Buchungen, die neueste gewinnt (z.B. 'rewe' -> Lebensmittel)."""
    by_word = {}
    bookings = Transaction.query.filter_by(user_id=user_id).order_by(Transaction.date.asc()).all()
    for booking in bookings:
        if booking.category_id in categories:
            for word in words(booking.description):
                by_word[word] = booking.category_id
    return by_word


def _suggest(row, by_word, categories):
    for word in words(row.counterparty) | words(row.purpose):
        category_id = by_word.get(word)
        if category_id and (categories[category_id] == 'income') == (row.amount > 0):
            return category_id
    return None


def build_preview(user_id, rows):
    counts = occurrences(rows)
    hashes = [fingerprint(r.day, r.amount, r.counterparty, r.purpose, n) for r, n in zip(rows, counts)]
    imported = {t.import_hash for t in Transaction.query.filter(
        Transaction.user_id == user_id, Transaction.import_hash.in_(hashes)).all()}
    categories = {c.id: c.type for c in Category.query.filter_by(user_id=user_id).all()}
    recurring = [(t, categories.get(t.category_id)) for t in
                 Transaction.query.filter_by(user_id=user_id, is_recurring=True).order_by(Transaction.id).all()]
    by_word = _suggestions(user_id, categories)
    used = set()

    result = []
    for row, key, occurrence in zip(rows, hashes, counts):
        entry = {
            "key": key, "occurrence": occurrence, "line": row.line, "date": row.day.isoformat(), "amount": row.amount,
            "counterparty": row.counterparty, "purpose": row.purpose,
            "description": description_for(row.counterparty, row.purpose),
            "status": 'new', "covered_by": None, "category_id": None,
        }
        if key in imported:
            entry["status"] = 'duplicate'
        else:
            booking = _covering_booking(row, recurring, used)
            if booking:
                entry["status"] = 'covered'
                entry["covered_by"] = {"id": booking.id, "description": booking.description, "amount": booking.amount}
            else:
                entry["category_id"] = _suggest(row, by_word, categories)
        result.append(entry)
    return result


def commit_rows(user_id, entries):
    """
    Legt die bestätigten Umsätze als einmalige Buchungen an. Der Fingerabdruck
    wird hier aus den Feldern neu berechnet; occurrence kommt aus der Vorschau,
    damit er auch stimmt, wenn von zwei gleichen Umsätzen nur einer übernommen
    wird. Schon importierte Umsätze werden übersprungen.
    Gibt (angelegt, übersprungen) zurück.
    """
    categories = {c.id: c.type for c in Category.query.filter_by(user_id=user_id).all()}
    # Erst alles prüfen, dann anlegen - ein Fehler in Zeile 80 soll nichts halb gespeichert lassen
    for entry in entries:
        kind = categories.get(entry.category_id)
        if kind is None:
            raise ApiError(404, 'Kategorie nicht gefunden')
        if (kind == 'income') != (entry.amount > 0):
            raise ApiError(400, f'{entry.description or entry.counterparty}: Einnahmen gehören in eine '
                                f'Einkommens-, Ausgaben in eine Ausgaben-Kategorie')

    created, skipped, keys = 0, 0, set()
    for entry in entries:
        key = fingerprint(entry.date, entry.amount, entry.counterparty, entry.purpose, entry.occurrence)
        if key in keys or Transaction.query.filter_by(user_id=user_id, import_hash=key).count():
            skipped += 1
            continue
        keys.add(key)
        db.session.add(Transaction(
            user_id=user_id, category_id=entry.category_id, amount=abs(entry.amount),
            description=entry.description or description_for(entry.counterparty, entry.purpose),
            date=datetime.combine(entry.date, datetime.min.time()), is_recurring=False, import_hash=key,
        ))
        created += 1
    db.session.commit()
    return created, skipped
