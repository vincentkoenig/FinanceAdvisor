"""
imports/bank_csv.py - Kontoumsätze aus dem CSV-Export einer Bank lesen.

Bewusst ohne festes Bankformat: Deutsche Banken exportieren ähnlich, aber nie
gleich (Semikolon oder Komma, UTF-8 oder Windows-1252, Kontoinfos über der
Kopfzeile, Betrag in einer Spalte oder getrennt nach Soll und Haben). Der
Leser sucht darum selbst die Kopfzeile und erkennt die Spalten an ihren
üblichen Namen. Klappt das nicht, kann der Aufrufer die Spalten von Hand
zuordnen (mapping) - die Antwort nennt dafür alle gefundenen Spalten.

Reine Verarbeitung ohne Datenbank und ohne KI; die Datei wird nirgends gespeichert.
"""

import csv
import io
import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional

# Bekannte Spaltennamen je Feld, kleingeschrieben und ohne Satzzeichen verglichen.
# Reihenfolge = Vorrang, falls mehrere passen (z.B. Buchungsdatum vor Valuta).
ALIASES = {
    'date': ['buchungsdatum', 'buchungstag', 'buchung', 'datum', 'umsatztag', 'valuta', 'valutadatum', 'wertstellung'],
    'amount': ['betrag', 'betrag eur', 'betrag in eur', 'betrag €', 'umsatz', 'umsatz in eur', 'betrag (eur)'],
    'debit': ['soll', 'ausgang', 'belastung'],
    'credit': ['haben', 'eingang', 'gutschrift'],
    'sign': ['soll/haben', 's/h', 'soll haben'],
    'counterparty': ['empfänger', 'empfaenger', 'zahlungsempfänger', 'auftraggeber', 'auftraggeber/empfänger',
                     'auftraggeber / empfänger', 'empfänger/zahlungspflichtiger', 'zahlungspflichtige/r',
                     'begünstigter/zahlungspflichtiger', 'name zahlungsbeteiligter', 'name', 'empfänger 1',
                     'beguenstigter/zahlungspflichtiger', 'gegenkonto name', 'zahlungsbeteiligter'],
    'purpose': ['verwendungszweck', 'vorgang/verwendungszweck', 'buchungstext', 'text', 'beschreibung',
                'umsatztext', 'verwendungszweck 1'],
    'currency': ['währung', 'waehrung', 'whrg', 'currency'],
}
FIELDS = tuple(ALIASES)

MAX_ROWS = 5000


class CsvImportError(ValueError):
    """Datei lässt sich nicht lesen. columns: gefundene Spalten, wenn eine Zuordnung helfen könnte."""

    def __init__(self, message, columns=None):
        super().__init__(message)
        self.columns = columns


@dataclass
class BankRow:
    line: int
    day: date
    amount: float          # Ausgaben negativ, Einnahmen positiv
    counterparty: str
    purpose: str


def _norm(text):
    return re.sub(r'\s+', ' ', re.sub(r'["\'.:]', '', text or '')).strip().lower()


def decode(data: bytes):
    """UTF-8 (mit oder ohne BOM), sonst Windows-1252 - so exportieren deutsche Banken."""
    for encoding in ('utf-8-sig', 'cp1252'):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise CsvImportError('Die Datei ist keine Textdatei (CSV).')


def _delimiter(lines):
    sample = '\n'.join(lines[:30])
    counts = {d: sample.count(d) for d in (';', ',', '\t')}
    return max(counts, key=counts.get)


def detect_mapping(header):
    """Spaltenindex je Feld anhand der bekannten Namen; nicht erkannte Felder fehlen."""
    names = [_norm(h) for h in header]
    mapping = {}
    for field, aliases in ALIASES.items():
        for alias in aliases:
            if alias in names and names.index(alias) not in mapping.values():
                mapping[field] = names.index(alias)
                break
    return mapping


def _usable(mapping):
    has_amount = 'amount' in mapping or ('debit' in mapping and 'credit' in mapping)
    return 'date' in mapping and has_amount and ('counterparty' in mapping or 'purpose' in mapping)


def parse_amount(text):
    """'-1.234,56' / '1234.56' / '1.234,56 €' / '- 12,00' -> float; leer -> None."""
    cleaned = re.sub(r'[€\s]|EUR', '', text or '')
    if not cleaned:
        return None
    negative = cleaned.startswith('-') or cleaned.endswith('-')
    cleaned = cleaned.strip('+-')
    if ',' in cleaned:
        cleaned = cleaned.replace('.', '').replace(',', '.')
    elif cleaned.count('.') > 1:
        cleaned = cleaned.replace('.', '')
    if not re.fullmatch(r'\d+(\.\d+)?', cleaned):
        raise ValueError(text)
    value = float(cleaned)
    return -value if negative else value


def parse_day(text):
    text = (text or '').strip()
    for pattern in ('%d.%m.%Y', '%d.%m.%y', '%Y-%m-%d', '%d/%m/%Y'):
        try:
            return datetime.strptime(text, pattern).date()
        except ValueError:
            continue
    raise ValueError(text)


def _find_header(rows):
    """Erste Zeile, aus der sich eine brauchbare Zuordnung ergibt (darüber stehen oft Kontoinfos)."""
    for index, row in enumerate(rows[:40]):
        if len(row) >= 3 and _usable(detect_mapping(row)):
            return index
    return None


def _widest_row(rows):
    """Ohne erkannte Kopfzeile: die erste Zeile mit den meisten Spalten gilt als Kopf (für die Zuordnung)."""
    width = max((len(r) for r in rows), default=0)
    return next((i for i, r in enumerate(rows) if len(r) == width), 0)


def read_bank_csv(data: bytes, mapping: Optional[dict] = None):
    """
    Liest die Umsätze. mapping (Feld -> Spaltenindex) überschreibt die Erkennung.
    Gibt (spalten, zuordnung, umsätze, übersprungene Zeilen) zurück.
    """
    text = decode(data)
    lines = [line for line in text.splitlines() if line.strip()]
    if not lines:
        raise CsvImportError('Die Datei ist leer.')
    rows = list(csv.reader(io.StringIO('\n'.join(lines)), delimiter=_delimiter(lines)))

    header_index = _find_header(rows)
    if mapping is None:
        if header_index is None:
            columns = rows[_widest_row(rows)]
            raise CsvImportError('Die Spalten wurden nicht erkannt. Bitte ordne sie zu.', columns=columns)
        mapping = detect_mapping(rows[header_index])
    else:
        header_index = header_index if header_index is not None else _widest_row(rows)
        if not _usable(mapping):
            raise CsvImportError('Bitte mindestens Datum, Betrag und Empfänger oder Verwendungszweck zuordnen.',
                                 columns=rows[header_index])
    columns = rows[header_index]

    def cell(row, field):
        index = mapping.get(field)
        return row[index].strip() if index is not None and index < len(row) else ''

    result, skipped = [], []
    for offset, row in enumerate(rows[header_index + 1:], start=header_index + 2):
        if len(result) >= MAX_ROWS:
            raise CsvImportError(f'Höchstens {MAX_ROWS} Umsätze pro Datei.')
        try:
            day = parse_day(cell(row, 'date'))
            if 'amount' in mapping:
                amount = parse_amount(cell(row, 'amount'))
            else:
                debit, credit = parse_amount(cell(row, 'debit')), parse_amount(cell(row, 'credit'))
                amount = (credit or 0) - abs(debit or 0) if debit or credit else None
            if amount is None:
                raise ValueError('kein Betrag')
            if _norm(cell(row, 'sign')) in ('s', 'soll'):
                amount = -abs(amount)
            currency = cell(row, 'currency').upper()
            if currency and currency not in ('EUR', '€'):
                skipped.append({"line": offset, "reason": f'Währung {currency}'})
                continue
        except ValueError:
            # Summenzeilen, Kontostand am Ende usw.
            skipped.append({"line": offset, "reason": 'kein Umsatz'})
            continue
        if amount == 0:
            continue
        result.append(BankRow(line=offset, day=day, amount=round(amount, 2),
                              counterparty=re.sub(r'\s+', ' ', cell(row, 'counterparty')),
                              purpose=re.sub(r'\s+', ' ', cell(row, 'purpose'))))

    if not result:
        raise CsvImportError('In der Datei wurden keine Umsätze gefunden.', columns=columns)
    return columns, mapping, result, skipped
