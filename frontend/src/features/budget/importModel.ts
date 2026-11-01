// Logik der Import-Seite ohne Oberfläche: Kategorien je Richtung, Auswahl und gemeinsame Zuordnung.
import type { Category } from '../../api/budget';
import type { CommitRow, ImportField, ImportRow } from '../../api/imports';

/** Felder der Spaltenzuordnung, wie sie die Seite abfragt */
export const MAPPING_FIELDS: { field: ImportField; label: string; required?: boolean }[] = [
  { field: 'date', label: 'Datum', required: true },
  { field: 'amount', label: 'Betrag (mit Vorzeichen)' },
  { field: 'debit', label: 'Soll / Ausgang' },
  { field: 'credit', label: 'Haben / Eingang' },
  { field: 'counterparty', label: 'Empfänger / Auftraggeber' },
  { field: 'purpose', label: 'Verwendungszweck' },
];

/** Kategorie-Auswahl für einen Umsatz: Einnahmen nur Einkommen, Ausgaben nur Fix- und variable Kosten */
export function categoryOptions(categories: Category[], income: boolean) {
  const types = income ? ['income'] : ['fixed_expense', 'variable_expense'];
  const mains = categories.filter((c) => c.parent_id === null && types.includes(c.type));
  return mains.flatMap((main) => {
    const subs = categories.filter((c) => c.parent_id === main.id);
    return subs.length ? subs.map((sub) => ({ id: sub.id, label: `${main.name} · ${sub.name}` })) : [{ id: main.id, label: main.name }];
  });
}

export type Choice = { selected: boolean; category: number | null; description: string };

/** Anfangszustand: neue Umsätze sind ausgewählt (mit Vorschlag, falls es einen gibt), die übrigen nicht */
export function initialChoices(rows: ImportRow[]): Record<string, Choice> {
  return Object.fromEntries(rows.map((row) => [row.key, {
    selected: row.status === 'new', category: row.category_id, description: row.description,
  }]));
}

/**
 * Kategorie für einen Umsatz setzen. Umsätze desselben Empfängers in derselben Richtung, die noch keine
 * Kategorie haben, bekommen sie gleich mit (zwölf Mal REWE muss man nicht zwölf Mal zuordnen).
 */
export function assignCategory(rows: ImportRow[], choices: Record<string, Choice>, key: string, category: number | null) {
  const row = rows.find((r) => r.key === key)!;
  const next = { ...choices, [key]: { ...choices[key], category } };
  if (category === null || !row.counterparty) return next;
  for (const other of rows) {
    const same = other.counterparty.toLowerCase() === row.counterparty.toLowerCase() && (other.amount > 0) === (row.amount > 0);
    if (same && other.status === 'new' && next[other.key].category === null) next[other.key] = { ...next[other.key], category };
  }
  return next;
}

/** Was übernommen wird; missing zählt ausgewählte Umsätze ohne Kategorie */
export function toCommit(rows: ImportRow[], choices: Record<string, Choice>) {
  const chosen = rows.filter((r) => r.status === 'new' && choices[r.key].selected);
  const missing = chosen.filter((r) => choices[r.key].category === null).length;
  const commit: CommitRow[] = chosen.filter((r) => choices[r.key].category !== null).map((r) => ({
    date: r.date, amount: r.amount, counterparty: r.counterparty, purpose: r.purpose, occurrence: r.occurrence,
    description: choices[r.key].description.trim() || r.description, category_id: choices[r.key].category!,
  }));
  return { commit, missing, total: chosen.length };
}
