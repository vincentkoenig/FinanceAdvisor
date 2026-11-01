"""
test_bank_csv.py - Unit Tests für den CSV-Leser der Kontoumsätze (imports/bank_csv.py).
Die Beispieldateien sind erfunden, aber so aufgebaut wie typische Exporte deutscher Banken.
"""

import sys
import os
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest

from fintrack.imports.bank_csv import CsvImportError, parse_amount, read_bank_csv

# Semikolon, Windows-1252, Kontoinfos über der Kopfzeile, Kontostand am Ende
WITH_PREAMBLE = (
    'Kontonummer;DE00 1234 5678 9000 0000 00\n'
    'Zeitraum;01.10.2026 - 31.10.2026\n'
    '\n'
    'Buchungsdatum;Valuta;Empfänger;Verwendungszweck;Betrag;Währung\n'
    '01.10.2026;01.10.2026;Beispiel Arbeitgeber GmbH;Gehalt Oktober;3.000,00;EUR\n'
    '02.10.2026;02.10.2026;Vermieter Müller;Miete Oktober;-1.200,00;EUR\n'
    '05.10.2026;05.10.2026;REWE Markt;Kartenzahlung;-54,90;EUR\n'
    '06.10.2026;06.10.2026;Hotel London;Kartenzahlung;-120,00;GBP\n'
    'Kontostand am 31.10.2026;;;;1.625,10;EUR\n'
).encode('cp1252')

# Komma, UTF-8 mit BOM, Soll und Haben in eigenen Spalten
DEBIT_CREDIT = (
    '﻿Buchungstag,Auftraggeber/Empfänger,Buchungstext,Soll,Haben\n'
    '2026-10-01,Beispiel Arbeitgeber GmbH,Lohn,,3000.00\n'
    '2026-10-03,Stadtwerke,Strom Abschlag,85.00,\n'
).encode('utf-8')


class TestAmounts:

    @pytest.mark.parametrize('text,expected', [
        ('-1.234,56', -1234.56), ('1234.56', 1234.56), ('1.234,56 €', 1234.56), ('- 12,00', -12.0),
        ('12,00-', -12.0), ('+3,20', 3.2), ('', None), ('1.000.000', 1000000.0),
    ])
    def test_parse_amount(self, text, expected):
        assert parse_amount(text) == expected


class TestReadBankCsv:

    def test_finds_header_below_account_info_and_skips_foreign_currency(self):
        columns, mapping, rows, skipped = read_bank_csv(WITH_PREAMBLE)

        assert columns[0] == 'Buchungsdatum'
        assert mapping['date'] == 0 and mapping['amount'] == 4
        assert [(r.day, r.amount, r.counterparty) for r in rows] == [
            (date(2026, 10, 1), 3000.0, 'Beispiel Arbeitgeber GmbH'),
            (date(2026, 10, 2), -1200.0, 'Vermieter Müller'),
            (date(2026, 10, 5), -54.9, 'REWE Markt'),
        ]
        assert [(s['line'], s['reason']) for s in skipped] == [(8, 'Währung GBP'), (9, 'kein Umsatz')]

    def test_debit_and_credit_columns(self):
        _, _, rows, _ = read_bank_csv(DEBIT_CREDIT)

        assert [(r.day, r.amount, r.purpose) for r in rows] == [
            (date(2026, 10, 1), 3000.0, 'Lohn'),
            (date(2026, 10, 3), -85.0, 'Strom Abschlag'),
        ]

    def test_sign_column(self):
        data = 'Datum;Name;Betrag;S/H\n01.10.2026;Laden;10,00;S\n02.10.2026;Erstattung;5,00;H\n'.encode()

        _, _, rows, _ = read_bank_csv(data)

        assert [r.amount for r in rows] == [-10.0, 5.0]

    def test_unknown_columns_ask_for_mapping(self):
        data = 'Tag;Wer;Wie viel\n01.10.2026;Laden;-10,00\n'.encode()

        with pytest.raises(CsvImportError) as error:
            read_bank_csv(data)

        assert error.value.columns == ['Tag', 'Wer', 'Wie viel']

    def test_manual_mapping(self):
        data = 'Tag;Wer;Wie viel\n01.10.2026;Laden;-10,00\n'.encode()

        _, _, rows, _ = read_bank_csv(data, {'date': 0, 'counterparty': 1, 'amount': 2})

        assert (rows[0].day, rows[0].amount, rows[0].counterparty) == (date(2026, 10, 1), -10.0, 'Laden')

    def test_incomplete_mapping_is_rejected(self):
        with pytest.raises(CsvImportError, match='mindestens Datum, Betrag'):
            read_bank_csv('Tag;Wer\n01.10.2026;Laden\n'.encode(), {'date': 0})

    @pytest.mark.parametrize('data,message', [
        (b'', 'leer'),
        ('Buchungsdatum;Empfänger;Betrag\nKontostand;;100\n'.encode(), 'keine Umsätze'),
    ])
    def test_empty_files(self, data, message):
        with pytest.raises(CsvImportError, match=message):
            read_bank_csv(data)
