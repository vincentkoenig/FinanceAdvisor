"""
imports/categorize.py - Kategorien für importierte Umsätze von der KI vorschlagen lassen.

Nur auf Knopfdruck in der Vorschau, für Umsätze ohne Vorschlag aus früheren Buchungen.
Gesendet werden ausschließlich die Namen der Empfänger bzw. Auftraggeber (jeder einmal) und
ob es eine Einnahme oder Ausgabe ist - keine Beträge, Daten, IBANs oder Verwendungszwecke.
Die Antwort wird geprüft: Es zählen nur Kategorien des Nutzers in der passenden Richtung
(Einnahmen -> Einkommen, Ausgaben -> Fix- oder variable Kosten). Passt keine, darf die KI eine
neue Unterkategorie unter einer vorhandenen Hauptkategorie vorschlagen (z.B. Versicherungen ->
Lebensversicherung); angelegt wird sie erst, wenn der Nutzer in der Vorschau zustimmt.
Gespeichert wird hier nichts.
"""

from typing import List, Optional

from pydantic import BaseModel as PydanticBaseModel

from fintrack.extensions import get_openai_client
from fintrack.models import Category

# So viele Namen je Anfrage an das Sprachmodell; mehr werden in Portionen geschickt
BATCH = 120


class _Choice(PydanticBaseModel):
    index: int
    category_id: Optional[int]
    # Nur wenn keine vorhandene Kategorie passt: neue Unterkategorie unter einer Hauptkategorie
    new_name: Optional[str]
    new_parent_id: Optional[int]


class _Answer(PydanticBaseModel):
    choices: List[_Choice]


INSTRUCTIONS = (
    'Du ordnest Umsätze eines deutschen Girokontos den Haushaltsbuch-Kategorien des Nutzers zu. Du bekommst die '
    'Kategorien (id, Name, Art) und eine nummerierte Liste von Empfängern bzw. Auftraggebern, jeweils mit Richtung '
    '(Ausgabe oder Einnahme). Gib für jeden Eintrag die passendste Kategorie-id zurück: Ausgaben nur Kategorien der '
    'Art Fixkosten oder variable Kosten, Einnahmen nur Kategorien der Art Einkommen. Setze category_id auf null, wenn '
    'du unsicher bist, wenn es eine Überweisung zwischen eigenen Konten, an einen Broker oder auf ein Depot ist (z.B. '
    'Trade Republic, Wertpapiergeschäft) oder wenn es sich um eine Privatperson ohne erkennbaren Zweck handelt. '
    'Bei Zahlungsdiensten (PayPal, Klarna) zählt der Händler hinter "·" bzw. "Purchase at". Erfinde keine ids. '
    'Nur wenn der Zweck klar erkennbar ist, aber keine vorhandene Kategorie passt (z.B. eine Lebensversicherung, '
    'aber es gibt keine solche Kategorie), lass category_id leer und schlage in new_name eine kurze neue '
    'Unterkategorie vor (ein bis zwei Wörter, z.B. "Lebensversicherung", "Fitnessstudio") und in new_parent_id die '
    'id der passenden Hauptkategorie aus der Liste der Hauptkategorien. Verwende für gleichartige Empfänger '
    'denselben neuen Namen. Sonst bleiben new_name und new_parent_id leer.'
)


def _allowed(user_id):
    """Wählbare Kategorien (Unterkategorien, sonst die Hauptkategorie) mit lesbarem Namen, nach Richtung."""
    categories = Category.query.filter_by(user_id=user_id).order_by(Category.id).all()
    with_children = {c.parent_id for c in categories if c.parent_id}
    by_id = {c.id: c for c in categories}
    labels, income, expense = {}, set(), set()
    for category in categories:
        # Umbuchungen bleiben dem Nutzer vorbehalten, die KI lässt eigene Konten ohnehin leer
        if category.id in with_children or category.is_transfer:
            continue
        main = by_id.get(category.parent_id) if category.parent_id else None
        labels[category.id] = f'{main.name} · {category.name}' if main else category.name
        (income if category.type == 'income' else expense).add(category.id)
    return labels, by_id, income, expense


def _ask(labels, by_id, payees):
    kinds = {'income': 'Einkommen', 'fixed_expense': 'Fixkosten', 'variable_expense': 'variable Kosten'}
    category_lines = '\n'.join(f'{cid}: {label} ({kinds.get(by_id[cid].type, by_id[cid].type)})'
                               for cid, label in labels.items())
    payee_lines = '\n'.join(f'{i}: {p["name"]} ({"Einnahme" if p["income"] else "Ausgabe"})' for i, p in enumerate(payees))
    response = get_openai_client().beta.chat.completions.parse(
        model="gpt-4o-mini",
        messages=[{"role": "system", "content": INSTRUCTIONS},
                  {"role": "user", "content": f'Kategorien:\n{category_lines}\n\nEmpfänger:\n{payee_lines}'}],
        temperature=0,
        response_format=_Answer,
    )
    return response.choices[0].message.parsed.choices


def _new_category(choice, income, by_id):
    """Vorschlag für eine neue Unterkategorie prüfen: Hauptkategorie des Nutzers in der passenden Richtung."""
    name = ' '.join((choice.new_name or '').split())[:60]
    parent = by_id.get(choice.new_parent_id)
    if not name or parent is None or parent.parent_id is not None or (parent.type == 'income') != income:
        return None, None
    # Gibt es die Unterkategorie schon, wird einfach sie genommen
    existing = next((c for c in by_id.values() if c.parent_id == parent.id and c.name.strip().lower() == name.lower()), None)
    if existing:
        return existing.id, None
    return None, {"name": name, "parent_id": parent.id, "parent_name": parent.name}


def suggest_categories(user_id, payees):
    """
    payees: [{"name": str, "income": bool}]. Gibt dieselbe Liste mit "category_id" (oder None) und
    "new_category" ({"name", "parent_id", "parent_name"} oder None) zurück.
    """
    labels, by_id, income_ids, expense_ids = _allowed(user_id)
    result = [{"name": p["name"], "income": p["income"], "category_id": None, "new_category": None} for p in payees]
    if not labels:
        return result
    for start in range(0, len(payees), BATCH):
        batch = payees[start:start + BATCH]
        for choice in _ask(labels, by_id, batch):
            if not 0 <= choice.index < len(batch):
                continue
            entry = result[start + choice.index]
            allowed = income_ids if entry["income"] else expense_ids
            if choice.category_id in allowed:
                entry["category_id"] = choice.category_id
            elif choice.category_id is None and choice.new_name:
                entry["category_id"], entry["new_category"] = _new_category(choice, entry["income"], by_id)
    return result
