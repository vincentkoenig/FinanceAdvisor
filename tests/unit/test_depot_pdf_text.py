"""
test_depot_pdf_text.py - PDFs mit IBM-Zeichennamen lesbar machen und den Empfänger im
Anschriftenfeld entfernen, bevor etwas an das Sprachmodell geht. Alle Daten sind erfunden.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from datetime import date

from fintrack.imports.depot_pdf import (ExtractedDocument, ExtractedTrade, apply_statement_figures, correct_trade_dates,
                                        decode_glyph_names, mask_personal_data)


def glyphs(text):
    """Baut Text so nach, wie ihn pypdf aus solchen PDFs liest."""
    signs = {' ': 'SP01', '(': 'SP06', ')': 'SP07', ',': 'SP08', '-': 'SP10', '.': 'SP11', '/': 'SP12', ':': 'SP13',
             '&': 'SM03', '*': 'SM04', '§': 'SM24', 'ä': 'LA17', 'ö': 'LO17', 'ü': 'LU17', 'ß': 'LS61', 'Ü': 'LU18'}
    def one(char):
        if char in signs:
            code = signs[char]
        elif char.isdigit():
            code = f'ND{int(char) or 10:02d}'
        else:
            code = f'L{char.upper()}{"02" if char.isupper() else "01"}'
        return f'/{code}0000'
    return ''.join(one(char) for char in text)


class TestDecodeGlyphNames:
    def test_reads_letters_digits_and_signs(self):
        sample = 'Wertpapier-Abrechnung: Köln & Söhne, Kurs 66,20 (EUR) 22.10.2020 A/B § 4 Maß'
        assert decode_glyph_names(glyphs(sample)) == sample

    def test_keeps_spaces_and_line_breaks_between_groups(self):
        assert decode_glyph_names(f"{glyphs('EUR')} {glyphs('12,50')}\n{glyphs('Ende')}") == 'EUR 12,50\nEnde'

    def test_leaves_normal_text_alone(self):
        text = 'Kauf 10 Stück /ISIN DE0007164600 zu 12,50 EUR'
        assert decode_glyph_names(text) == text

    def test_joins_letter_spaced_headings(self):
        heading = glyphs('W e r t p a p i e r - A b r e c h n u n g   V e r k a u f')
        assert decode_glyph_names(f"{heading}\n{glyphs('ST 1 EUR 66,20')}") == 'Wertpapier-Abrechnung   Verkauf\nST 1 EUR 66,20'

    def test_unknown_sign_becomes_question_mark(self):
        assert decode_glyph_names('/LA020000/SD990000/LB020000') == 'A?B'


def document(*days, quantity=1, price=1):
    return ExtractedDocument(is_trade_statement=True, note=None, trades=[
        ExtractedTrade(type='buy', isin='US0378331005', name='Beispiel', trade_date=day, quantity=quantity, price=price, fees=0, currency='EUR')
        for day in days
    ])


class TestApplyStatementFigures:
    SAVINGS_PLAN = ('ST 0,683 BEISPIEL MSCI EUR.SRI LU1861137484\n[NUMMER]     01.10.2021  1\n'
                    'EUR 71,75 01.10.2021  Girosammelverwahrung\nKurswert EUR 49,01  Wertpapierprovision* EUR 0,98')

    def test_page_number_is_not_the_quantity(self):
        trade = apply_statement_figures(document(date(2021, 10, 1), price=49.01), self.SAVINGS_PLAN).trades[0]
        assert trade.quantity == 0.683
        assert round(trade.price * trade.quantity, 2) == 49.01

    def test_price_from_the_statement_stays_when_it_fits(self):
        trade = apply_statement_figures(document(date(2021, 10, 1), quantity=0.683, price=71.75), self.SAVINGS_PLAN).trades[0]
        assert trade.price == 71.75

    def test_thousands_in_quantity_and_market_value(self):
        text = 'ST 1.200\nBEISPIEL AG\n[NUMMER] 04.11.2020 1\nKurswert EUR 3.426,00'
        trade = apply_statement_figures(document(date(2020, 11, 4), price=3426), text).trades[0]
        assert (trade.quantity, trade.price) == (1200, 2.855)

    def test_corporate_action_is_not_booked(self):
        result = apply_statement_figures(document(date(2022, 8, 25), price=2.5), 'Abrechnung Kapitalmaßnahme\nST 8\nTESLA')
        assert (result.is_trade_statement, result.trades) == (False, [])
        assert 'Aktiensplit' in result.note

    def test_documents_with_several_trades_are_left_alone(self):
        result = apply_statement_figures(document(date(2024, 1, 2), date(2024, 1, 3)), 'ST 5\nKurswert EUR 10,00')
        assert [t.quantity for t in result.trades] == [1, 1]


class TestCorrectTradeDates:
    TEXT = '[NUMMER] 22.10.2020 1\n22.10.2020\nKurswert EUR 66,20\nValuta 26.10.2020 ------\n09.04.11'

    def test_scrambled_year_becomes_the_date_in_the_document(self):
        assert correct_trade_dates(document(date(2210, 10, 20)), self.TEXT).trades[0].trade_date == date(2020, 10, 22)

    def test_correct_date_stays_even_if_it_is_the_value_date(self):
        assert correct_trade_dates(document(date(2020, 10, 26)), self.TEXT).trades[0].trade_date == date(2020, 10, 26)

    def test_several_days_use_the_same_month(self):
        text = '01.03.2024 Kauf\n15.04.2024 Kauf'
        result = correct_trade_dates(document(date(2401, 3, 20)), text)
        assert result.trades[0].trade_date == date(2024, 3, 1)

    def test_unclear_date_stays_and_asks_for_a_check(self):
        text = '01.03.2024 Kauf\n15.03.2024 Kauf'
        result = correct_trade_dates(document(date(2401, 3, 20)), text)
        assert result.trades[0].trade_date == date(2401, 3, 20)
        assert 'Datum von Beispiel prüfen' in result.note

    def test_document_without_german_dates_is_left_alone(self):
        result = correct_trade_dates(document(date(2024, 3, 1)), '2024-03-01 Kauf')
        assert result.trades[0].trade_date == date(2024, 3, 1)


class TestRecipientIsRemoved:
    STATEMENT = '\n'.join([
        'Wertpapier-Abrechnung',
        'Depotnummer Abrechnungstag',
        'Herrn und Frau',
        '01.02.03',
        'Muster Erika,',
        'Muster-Beispiel Max',
        'Teststr. 12',
        '12345 Beispielstadt',
        'Depot',
        '430 12345678',
        'Muster Erika,',
        'Muster-Beispiel Max',
        'BEISPIEL & CO. INC.',
        'US0378331005',
        'Kurswert EUR 66,20',
    ] + ['Zeile'] * 3)

    def test_names_and_address_are_gone_also_where_they_repeat(self):
        masked = mask_personal_data(self.STATEMENT)
        for private in ('Erika', 'Max', 'Teststr', '12345', 'Beispielstadt', '12345678'):
            assert private not in masked

    def test_trade_details_stay(self):
        masked = mask_personal_data(self.STATEMENT)
        for detail in ('BEISPIEL & CO. INC.', 'US0378331005', 'Kurswert EUR 66,20'):
            assert detail in masked

    def test_address_after_line_15_is_found(self):
        masked = mask_personal_data('\n'.join(['Kopf'] * 20) + '\nHerrn\nErika Muster\nTeststr. 12\n12345 Ort\nKurs 5,00')
        assert 'Erika' not in masked and 'Teststr' not in masked and 'Kurs 5,00' in masked

    def test_contact_person_without_space_is_removed(self):
        assert 'Muster' not in mask_personal_data('FrauMuster\nKurs 5,00')

    def test_without_postcode_nothing_is_cut(self):
        masked = mask_personal_data('Frau Muster betreut Sie\nKurswert EUR 66,20\nStück 3')
        assert 'Kurswert EUR 66,20' in masked and 'Stück 3' in masked
