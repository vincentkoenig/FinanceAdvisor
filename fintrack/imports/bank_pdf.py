"""
imports/bank_pdf.py - Kontoumsätze aus einem Kontoauszug als PDF lesen.

Gleicher Weg wie bei Depot-Abrechnungen (imports/depot_pdf.py): Text aus dem PDF holen,
persönliche Angaben entfernen, den Rest vom Sprachmodell als festes Schema auslesen
lassen. Heraus kommen dieselben Umsätze (BankRow) wie aus einem CSV-Export, danach
laufen Vorschau, Abgleich und Dubletten-Schutz wie beim CSV-Import.

Gegenüber und Verwendungszweck bleiben im Text stehen (sonst ließe sich nichts zuordnen);
entfernt werden Name und Adresse des Kontoinhabers, IBANs, Kunden- und Kontonummern.
"""

from datetime import date
from typing import List, Optional

from pydantic import BaseModel as PydanticBaseModel

from fintrack.extensions import get_openai_client
from fintrack.imports.bank_csv import BankRow


class ExtractedBankRow(PydanticBaseModel):
    booking_date: date
    # Ausgaben/Belastungen negativ, Einnahmen/Gutschriften positiv, in Euro
    amount: float
    counterparty: str
    purpose: str


class ExtractedStatement(PydanticBaseModel):
    # False, wenn das PDF kein Kontoauszug bzw. keine Umsatzliste ist
    is_bank_statement: bool
    rows: List[ExtractedBankRow]
    note: Optional[str]


INSTRUCTIONS = (
    'Du liest den Text eines deutschen Kontoauszugs oder einer Umsatzliste (z.B. HypoVereinsbank, Sparkasse). '
    'Gib jeden einzelnen Umsatz als eigenen Eintrag zurück: Buchungsdatum, Betrag in Euro (Belastungen/Soll/Ausgaben '
    'negativ, Gutschriften/Haben/Einnahmen positiv), Gegenüber (Empfänger bzw. Auftraggeber, ohne IBAN) und '
    'Verwendungszweck (kurz, ohne Mandats- und Gläubiger-IDs). Kontostände, Saldo-, Übertrags- und Summenzeilen '
    'sind keine Umsätze. Fehlt beim Datum das Jahr, nimm das Jahr aus dem Auszugszeitraum. '
    'Ist das Dokument kein Kontoauszug, setze is_bank_statement auf false und gib keine Einträge zurück. Erfinde '
    'nichts; ist ein Umsatz unleserlich, lass ihn weg und erkläre es in note. Persönliche Angaben sind durch '
    'Platzhalter wie [NUMMER] ersetzt.'
)


def read_statement(masked_text):
    """Schickt den maskierten Text an das Sprachmodell und gibt ExtractedStatement zurück."""
    response = get_openai_client().beta.chat.completions.parse(
        model="gpt-4o-mini",
        messages=[{"role": "system", "content": INSTRUCTIONS}, {"role": "user", "content": masked_text}],
        temperature=0,
        response_format=ExtractedStatement,
    )
    return response.choices[0].message.parsed


def to_bank_rows(statement):
    """Ausgelesene Umsätze als BankRow wie aus dem CSV-Leser; Nullbeträge fallen weg."""
    rows = []
    for number, row in enumerate(statement.rows, start=1):
        amount = round(row.amount, 2)
        if amount == 0:
            continue
        rows.append(BankRow(line=number, day=row.booking_date, amount=amount,
                            counterparty=' '.join(row.counterparty.split())[:500],
                            purpose=' '.join(row.purpose.split())[:1000]))
    return rows
