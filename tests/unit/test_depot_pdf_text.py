"""
test_depot_pdf_text.py - PDFs mit IBM-Zeichennamen lesbar machen und den Empfänger im
Anschriftenfeld entfernen, bevor etwas an das Sprachmodell geht. Alle Daten sind erfunden.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from fintrack.imports.depot_pdf import decode_glyph_names, mask_personal_data


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
