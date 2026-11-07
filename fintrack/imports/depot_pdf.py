"""
imports/depot_pdf.py - Käufe und Verkäufe aus PDF-Abrechnungen von Brokern lesen
(z.B. Trade Republic, HypoVereinsbank-Depot).

Ablauf:
1. Text aus dem PDF holen (pypdf), die Datei wird nicht gespeichert
2. Persönliches entfernen, bevor etwas das Haus verlässt: IBAN, Kunden-, Depot- und
   Auftragsnummern, Adressblock, E-Mail, Telefon (mask_personal_data)
3. Der maskierte Text geht an das Sprachmodell, das die Abrechnung als festes Schema
   zurückgibt (Structured Output, wie bei der Portfolio-Analyse)

Formate einzelner Broker sind bewusst nicht fest programmiert: Abrechnungen ändern
ihr Layout, das Sprachmodell kommt damit zurecht. Geprüft wird das Ergebnis danach
trotzdem (Stück, Kurs, ISIN), und gebucht wird erst nach Bestätigung.
"""

import io
import re
from datetime import date
from typing import List, Literal, Optional

from pydantic import BaseModel as PydanticBaseModel
from pypdf import PdfReader
from pypdf.errors import PdfReadError

from fintrack.extensions import get_openai_client

MAX_PAGES = 20
MAX_CHARS = 30_000

ISIN = re.compile(r'\b[A-Z]{2}[A-Z0-9]{9}\d\b')

# Manche Banken (z.B. die HypoVereinsbank) drucken mit IBM-Schriften ohne Zeichentabelle: Statt
# Buchstaben stehen im PDF deren IBM-Namen (GCGID), z.B. /LB020000 für "B" und /ND100000 für "0".
_GLYPH = re.compile(r'/([A-Z]{2})(\d{2})0000')
_SPACED_WORD = re.compile(r'(?<!\S)(?:[A-Za-zÄÖÜäöüß-] ){3,}[A-Za-zÄÖÜäöüß-](?!\S)')
_GLYPH_SIGNS = {
    'SP01': ' ', 'SP02': '!', 'SP05': "'", 'SP06': '(', 'SP07': ')', 'SP08': ',', 'SP09': '_', 'SP10': '-', 'SP11': '.',
    'SP12': '/', 'SP13': ':', 'SP14': ';', 'SP15': '?', 'SM03': '&', 'SM04': '*', 'SM24': '§',
    'LA17': 'ä', 'LA18': 'Ä', 'LO17': 'ö', 'LO18': 'Ö', 'LU17': 'ü', 'LU18': 'Ü', 'LS61': 'ß',
}


def _read_glyph(match):
    kind, number = match.group(1), int(match.group(2))
    if kind == 'ND' and 1 <= number <= 10:
        return str(number % 10)
    if kind[0] == 'L' and number in (1, 2):
        return kind[1].lower() if number == 1 else kind[1]
    return _GLYPH_SIGNS.get(f'{kind}{number:02d}', '?')


def decode_glyph_names(text):
    """
    Übersetzt IBM-Zeichennamen in Text. Normaler Text bleibt, wie er ist. Gesperrte Überschriften
    ("V e r k a u f") rückt sie zusammen: Sie sagen, ob es Kauf oder Verkauf ist.
    """
    if not _GLYPH.search(text):
        return text
    return _SPACED_WORD.sub(lambda match: match.group(0).replace(' ', ''), _GLYPH.sub(_read_glyph, text))


_PATTERNS = [
    # IBAN (mit oder ohne Leerzeichen)
    (re.compile(r'\b[A-Z]{2}\d{2}(?:\s?[A-Z0-9]{4}){3,7}(?:\s?[A-Z0-9]{1,4})?\b'), '[IBAN]'),
    (re.compile(r'[\w.+-]+@[\w-]+\.[\w.]+'), '[E-MAIL]'),
    (re.compile(r'(?:\+49|0049|\b0)[\d /()-]{8,}\d'), '[TELEFON]'),
    # Nur im Briefkopf (siehe ADDRESS_LINES): Postleitzahl + Ort, z.B. "80331 München"
    (re.compile(r'\b\d{5}\s+[A-ZÄÖÜ][\wäöüß.-]+(?:\s+[\wäöüß.-]+)?'), '[ORT]'),
    # Straße mit Hausnummer, z.B. "Musterstraße 12a"
    (re.compile(r'\b[A-ZÄÖÜ][\wäöüß.-]*(?:straße|str\.|weg|platz|allee|gasse|ring|damm)\s+\d+\s?[a-z]?\b', re.I), '[STRASSE]'),
]
# Lange Ziffernfolgen (Kunden-, Depot-, Auftragsnummern); Beträge haben Komma oder Punkt und bleiben
_NUMBER = re.compile(r'(?<![\d,.])\d[\d ]{6,}\d(?![\d,.])')
# Zeilen mit Anrede oder Kennnummern ganz weglassen
_PERSONAL_LINE = re.compile(r'^\s*(herrn?|frau|kunde|kundennummer|depotnummer|depot-nr|konto|kontonummer|'
                            r'steuer-?id|steuernummer|bic|iban)\b', re.I)


# Adresse und Straße stehen oben im Briefkopf; weiter unten könnten die Muster Beträge treffen
ADDRESS_LINES = 15
# Empfänger im Anschriftenfeld: nach der Anrede bis zur Zeile mit Postleitzahl und Ort
# Ansprechpartner ohne Leerzeichen, z.B. "FrauMuster" im Kopf von HVB-Abrechnungen
_GLUED_NAME = re.compile(r'^\s*(Herrn?|Frau)[A-ZÄÖÜ]')
_SALUTATION = re.compile(r'^\s*(herrn?|frau)\b', re.I)
_POSTCODE_LINE = re.compile(r'^\s*\d{5}\s+\S')
RECIPIENT_LINES = 6


def _recipient_lines(lines):
    """
    Zeilennummern mit dem Empfänger, auch an anderer Stelle im Dokument: Abrechnungen nennen
    die Depotinhaber oft ein zweites Mal, und Namen haben kein Muster wie eine IBAN.
    """
    key = lambda line: line.strip().rstrip(',').lower()
    hidden, known = set(), set()
    for start, line in enumerate(lines):
        if not _SALUTATION.match(line):
            continue
        block = lines[start + 1:start + 1 + RECIPIENT_LINES]
        end = next((index for index, entry in enumerate(block) if _POSTCODE_LINE.match(entry)), None)
        if end is not None:
            hidden.update(range(start + 1, start + end + 2))
            known.update(key(entry) for entry in block[:end + 1] if key(entry))
    hidden.update(index for index, line in enumerate(lines) if key(line) in known)
    return hidden


def mask_personal_data(text):
    """Entfernt persönliche Angaben; ISINs, Beträge, Daten und Stückzahlen bleiben."""
    lines = []
    source = text.splitlines()
    recipient = _recipient_lines(source)
    for number, line in enumerate(source):
        if number in recipient or _PERSONAL_LINE.match(line) or _GLUED_NAME.match(line):
            lines.append('[ENTFERNT]')
            continue
        isins = {}

        def keep_isin(match):
            isins[f'@@{len(isins)}@@'] = match.group(0)
            return f'@@{len(isins) - 1}@@'

        line = ISIN.sub(keep_isin, line)
        for index, (pattern, label) in enumerate(_PATTERNS):
            if index >= 3 and number >= ADDRESS_LINES:
                break
            line = pattern.sub(label, line)
        line = _NUMBER.sub('[NUMMER]', line)
        for placeholder, isin in isins.items():
            line = line.replace(placeholder, isin)
        lines.append(line)
    return '\n'.join(lines)


class PdfImportError(ValueError):
    pass


def extract_text(data: bytes):
    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            raise PdfImportError('Das PDF ist passwortgeschützt.')
        if len(reader.pages) > MAX_PAGES:
            raise PdfImportError(f'Höchstens {MAX_PAGES} Seiten pro PDF.')
        text = decode_glyph_names('\n'.join(page.extract_text() or '' for page in reader.pages))
    except (PdfReadError, ValueError, KeyError) as error:
        if isinstance(error, PdfImportError):
            raise
        raise PdfImportError('Die Datei ist kein lesbares PDF.') from error
    if not text.strip():
        raise PdfImportError('Im PDF steht kein Text (vermutlich ein Scan).')
    return text[:MAX_CHARS]


# ─── SCHEMA FÜR DAS SPRACHMODELL ──────────────────────────────────────────────

class ExtractedTrade(PydanticBaseModel):
    type: Literal['buy', 'sell']
    isin: str
    name: str
    trade_date: date
    quantity: float
    # Kurs je Stück in Euro, ohne Gebühren
    price: float
    # Summe aller Gebühren/Provisionen in Euro (0, wenn keine)
    fees: float
    currency: str


class ExtractedDocument(PydanticBaseModel):
    # False, wenn das PDF keine Kauf-/Verkaufsabrechnung ist (z.B. Depotauszug, Dividende)
    is_trade_statement: bool
    trades: List[ExtractedTrade]
    note: Optional[str]


INSTRUCTIONS = (
    'Du liest den Text einer deutschen Wertpapierabrechnung (z.B. Trade Republic, HypoVereinsbank, Sparplan). '
    'Gib jede Kauf- und Verkaufsausführung als eigenen Eintrag zurück: Art (buy/sell), ISIN, Name des Wertpapiers, '
    'Ausführungs- bzw. Handelstag, Stückzahl, Ausführungskurs je Stück in Euro (ohne Gebühren), die Summe aller '
    'Gebühren und Provisionen in Euro (Steuern nicht) und die Währung des Kurses. Wenn der Kurs in einer anderen '
    'Währung steht, rechne mit dem in der Abrechnung genannten Devisenkurs in Euro um. '
    'Ist das Dokument keine Kauf- oder Verkaufsabrechnung (z.B. Depotauszug, Dividende, Kostenausweis), setze '
    'is_trade_statement auf false und gib keine Einträge zurück. Erfinde nichts; fehlt eine Angabe, lass den '
    'Eintrag weg und erkläre es in note. Persönliche Angaben sind durch Platzhalter wie [NUMMER] ersetzt.'
)


def read_trades(masked_text):
    """Schickt den maskierten Text an das Sprachmodell und gibt ExtractedDocument zurück."""
    response = get_openai_client().beta.chat.completions.parse(
        model="gpt-4o-mini",
        messages=[{"role": "system", "content": INSTRUCTIONS}, {"role": "user", "content": masked_text}],
        temperature=0,
        response_format=ExtractedDocument,
    )
    return response.choices[0].message.parsed
