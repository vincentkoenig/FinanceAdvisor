"""
imports/trade_republic_csv.py - Käufe und Verkäufe aus dem Transaktionsexport von Trade Republic
(CSV, Profil -> Transaktionen exportieren) lesen, ohne KI.

Das Format ist fest (englische Spaltennamen, Punkt als Dezimaltrenner):
- category TRADING, type BUY/SELL: eine Ausführung; shares beim Verkauf negativ, price in Euro
  je Stück ohne Gebühr, fee negativ
- category CORPORATE_ACTION, type SPLIT: shares = neu eingebuchte Stücke. Frühere Ausführungen
  derselben ISIN werden auf das neue Verhältnis umgerechnet (mehr Stück, kleinerer Kurs), wie
  es auch die Kurshistorie von Yahoo tut - sonst stimmen Bestand und Wert nach dem Split nicht.
- alles andere (Ein-/Auszahlungen, Dividenden, Zinsen) wird übersprungen; Dividenden bucht
  FinTrack selbst aus dem Bestand
Ergebnis sind ExtractedTrade wie aus einer PDF-Abrechnung; Vorschau und Buchen laufen gemeinsam.
"""

import csv
import io
from collections import defaultdict

from fintrack.imports.bank_csv import CsvImportError, decode
from fintrack.imports.crypto_csv import MAX_ROWS, parse_timestamp
from fintrack.imports.depot_pdf import ISIN, ExtractedTrade

REQUIRED = {'datetime', 'category', 'type', 'asset_class', 'name', 'symbol', 'shares', 'price', 'amount', 'fee',
            'currency', 'transaction_id'}
SKIP_TEXT = {
    'CUSTOMER_INBOUND': 'Einzahlung', 'CUSTOMER_INPAYMENT': 'Einzahlung', 'TRANSFER_INSTANT_INBOUND': 'Einzahlung',
    'CUSTOMER_OUTBOUND_REQUEST': 'Auszahlung', 'TRANSFER_INSTANT_OUTBOUND': 'Auszahlung',
    'DIVIDEND': 'Dividende', 'DISTRIBUTION': 'Ausschüttung', 'EARNINGS': 'Ertrag', 'INTEREST_PAYMENT': 'Zinsen',
}
QUANTITY_EPSILON = 1e-9


def is_trade_republic(data: bytes):
    """True, wenn die erste Zeile die Kopfzeile des Trade-Republic-Exports ist."""
    first = decode(data).lstrip().split('\n', 1)[0]
    return REQUIRED <= {name.strip().strip('"').lower() for name in first.split(',')}


def _number(text):
    text = (text or '').strip()
    return float(text) if text else 0.0


def read_trade_republic_csv(data: bytes):
    """Gibt (spalten, zuordnung, trades, übersprungen) zurück, wie read_crypto_csv."""
    rows = list(csv.DictReader(io.StringIO(decode(data))))
    if len(rows) > MAX_ROWS:
        raise CsvImportError(f'Höchstens {MAX_ROWS} Zeilen pro Datei.')
    columns = list(rows[0].keys()) if rows else []

    # Zeilennummer in der Datei merken, dann zeitlich sortieren (der Export ist meist schon sortiert)
    numbered = sorted(enumerate(rows, start=2), key=lambda item: item[1].get('datetime') or '')
    trades, skipped = [], []
    by_isin = defaultdict(list)
    held = defaultdict(float)

    for line, row in numbered:
        category, kind = (row.get('category') or '').upper(), (row.get('type') or '').upper()
        isin = (row.get('symbol') or '').strip().upper()
        try:
            day = parse_timestamp(row.get('date') or row.get('datetime'))
            shares = _number(row.get('shares'))
            price = _number(row.get('price'))
            fee = abs(_number(row.get('fee')))
        except ValueError:
            skipped.append({"line": line, "reason": 'nicht lesbar'})
            continue

        if category == 'CORPORATE_ACTION' and kind == 'SPLIT' and ISIN.fullmatch(isin):
            if held[isin] > QUANTITY_EPSILON and held[isin] + shares > QUANTITY_EPSILON:
                ratio = (held[isin] + shares) / held[isin]
                for index in by_isin[isin]:
                    before = trades[index]
                    trades[index] = before.model_copy(update={
                        'quantity': before.quantity * ratio, 'price': round(before.price / ratio, 6)})
                held[isin] += shares
            else:
                skipped.append({"line": line, "reason": 'Split ohne Bestand'})
            continue

        if category != 'TRADING' or kind not in ('BUY', 'SELL'):
            skipped.append({"line": line, "reason": SKIP_TEXT.get(kind, kind.title() or 'keine Art')})
            continue
        currency = (row.get('currency') or 'EUR').strip().upper()
        if not ISIN.fullmatch(isin) or not shares or price <= 0 or currency != 'EUR':
            skipped.append({"line": line, "reason": 'keine ISIN, Stückzahl oder kein Kurs in Euro'})
            continue

        trade_type = 'buy' if kind == 'BUY' else 'sell'
        quantity = abs(shares)
        held[isin] += quantity if trade_type == 'buy' else -quantity
        by_isin[isin].append(len(trades))
        trades.append(ExtractedTrade(type=trade_type, isin=isin, name=(row.get('name') or isin).strip(), trade_date=day,
                                     quantity=quantity, price=price, fees=round(fee, 2), currency='EUR'))

    if not trades:
        raise CsvImportError('In der Datei wurden keine Käufe oder Verkäufe gefunden.')
    return columns, {}, trades, skipped
