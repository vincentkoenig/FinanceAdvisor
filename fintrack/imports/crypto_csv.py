"""
imports/crypto_csv.py - Krypto-Käufe und -Verkäufe aus dem CSV-Export einer App oder Börse
(z.B. Bison) lesen.

Wie beim Kontoimport ohne festes Format: Kopfzeile suchen, Spalten an üblichen deutschen und
englischen Namen erkennen, sonst Zuordnung von Hand. Nur Käufe und Verkäufe zählen; Ein- und
Auszahlungen, Überträge, Staking usw. werden übersprungen und gemeldet.
Ergebnis sind dieselben Einträge wie aus einer Depot-Abrechnung (ExtractedTrade), mit dem
Kürzel der Kryptowährung statt einer ISIN - Vorschau und Buchen laufen danach gemeinsam.
"""

import csv
import io
import re
from datetime import datetime

from fintrack.imports.bank_csv import CsvImportError, _delimiter, _norm, decode, parse_amount
from fintrack.imports.depot_pdf import ExtractedTrade

ALIASES = {
    'date': ['datum', 'date', 'zeitpunkt', 'transaction date', 'transaktionsdatum', 'timestamp', 'time', 'zeit',
             'created at', 'ausführungsdatum', 'handelsdatum'],
    'type': ['typ', 'type', 'transaction type', 'transaktionstyp', 'art', 'transaktion', 'side', 'vorgang'],
    'asset': ['asset', 'kryptowährung', 'kryptowaehrung', 'coin', 'cryptocurrency', 'krypto', 'währung krypto',
              'asset symbol', 'symbol', 'kryptowert', 'digital asset'],
    'quantity': ['menge', 'anzahl', 'amount', 'asset amount', 'quantity', 'crypto amount', 'kryptomenge', 'stück',
                 'betrag krypto', 'amount asset'],
    'price': ['kurs', 'preis', 'price', 'asset price', 'price per coin', 'rate', 'kurs eur', 'preis eur',
              'asset market price', 'price (eur)'],
    'total': ['betrag', 'betrag eur', 'eur', 'total', 'value', 'gesamt', 'gesamtbetrag', 'fiat amount',
              'amount eur', 'eur amount', 'wert', 'wert eur', 'total (eur)'],
    'fee': ['gebühr', 'gebühren', 'gebuehr', 'fee', 'fees', 'gebühr eur', 'fee (eur)'],
}
FIELDS = tuple(ALIASES)

BUY_WORDS = ('buy', 'kauf', 'purchase', 'gekauft', 'bought')
SELL_WORDS = ('sell', 'verkauf', 'verkauft', 'sold')
TICKER = re.compile(r'^[A-Z0-9]{2,10}$')
MAX_ROWS = 5000


def detect_mapping(header):
    names = [_norm(h) for h in header]
    mapping = {}
    for field, aliases in ALIASES.items():
        for alias in aliases:
            if alias in names and names.index(alias) not in mapping.values():
                mapping[field] = names.index(alias)
                break
    return mapping


def _usable(mapping):
    has_price = 'price' in mapping or 'total' in mapping
    return all(field in mapping for field in ('date', 'type', 'asset', 'quantity')) and has_price


def parse_timestamp(text):
    """'2026-10-01 12:34:56', '2026-10-01T12:34:56Z', '01.10.2026 12:34', '01.10.2026' -> date"""
    text = (text or '').strip()
    match = re.match(r'(\d{4}-\d{2}-\d{2})|(\d{2}\.\d{2}\.\d{4})|(\d{2}/\d{2}/\d{4})', text)
    if not match:
        raise ValueError(text)
    part = match.group(0)
    for pattern in ('%Y-%m-%d', '%d.%m.%Y', '%d/%m/%Y'):
        try:
            return datetime.strptime(part, pattern).date()
        except ValueError:
            continue
    raise ValueError(text)


def _kind(text):
    value = _norm(text)
    if any(word in value for word in SELL_WORDS):
        return 'sell'
    if any(word in value for word in BUY_WORDS):
        return 'buy'
    return None


def read_crypto_csv(data: bytes, mapping=None):
    """
    Gibt (spalten, zuordnung, trades, übersprungen) zurück. trades sind ExtractedTrade mit dem
    Kürzel (z.B. "BTC") im Feld isin; der Kurs ist je Einheit in Euro ohne Gebühr.
    """
    text = decode(data)
    lines = text.splitlines()
    filled = [line for line in lines if line.strip()]
    if not filled:
        raise CsvImportError('Die Datei ist leer.')
    rows = list(csv.reader(io.StringIO('\n'.join(lines)), delimiter=_delimiter(filled)))

    header_index = next((i for i, row in enumerate(rows[:40]) if len(row) >= 4 and _usable(detect_mapping(row))), None)
    if mapping is None:
        if header_index is None:
            widest = max(range(len(rows)), key=lambda i: len(rows[i]))
            raise CsvImportError('Die Spalten wurden nicht erkannt. Bitte ordne sie zu.', columns=rows[widest])
        mapping = detect_mapping(rows[header_index])
    else:
        if header_index is None:
            header_index = max(range(len(rows)), key=lambda i: len(rows[i]))
        if not _usable(mapping):
            raise CsvImportError('Bitte mindestens Datum, Art, Kryptowährung, Menge und Kurs oder Betrag zuordnen.',
                                 columns=rows[header_index])
    columns = rows[header_index]

    def cell(row, field):
        index = mapping.get(field)
        return row[index].strip() if index is not None and index < len(row) else ''

    trades, skipped = [], []
    for line, row in enumerate(rows[header_index + 1:], start=header_index + 2):
        if not any(value.strip() for value in row):
            continue
        if len(trades) >= MAX_ROWS:
            raise CsvImportError(f'Höchstens {MAX_ROWS} Zeilen pro Datei.')
        kind = _kind(cell(row, 'type'))
        if kind is None:
            skipped.append({"line": line, "reason": cell(row, 'type') or 'keine Art'})
            continue
        try:
            day = parse_timestamp(cell(row, 'date'))
            quantity = abs(parse_amount(cell(row, 'quantity')) or 0)
            price = parse_amount(cell(row, 'price')) if 'price' in mapping else None
            total = parse_amount(cell(row, 'total')) if 'total' in mapping else None
            fee = abs(parse_amount(cell(row, 'fee')) or 0) if 'fee' in mapping else 0.0
        except ValueError:
            skipped.append({"line": line, "reason": 'nicht lesbar'})
            continue
        asset = re.sub(r'[^A-Z0-9]', '', cell(row, 'asset').upper())
        if not quantity or not TICKER.match(asset) or asset in ('EUR', 'USD'):
            skipped.append({"line": line, "reason": 'keine Menge oder Kryptowährung'})
            continue
        if not price:
            if not total:
                skipped.append({"line": line, "reason": 'kein Kurs'})
                continue
            price = abs(total) / quantity
        trades.append(ExtractedTrade(type=kind, isin=asset, name=asset, trade_date=day, quantity=quantity,
                                     price=round(abs(price), 6), fees=round(fee, 2), currency='EUR'))

    if not trades:
        raise CsvImportError('In der Datei wurden keine Käufe oder Verkäufe gefunden.', columns=columns)
    return columns, mapping, trades, skipped
