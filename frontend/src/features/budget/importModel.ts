// Logik der Import-Seite ohne Oberfläche: Kategorien je Richtung, Auswahl und gemeinsame Zuordnung.
import type { Category } from '../../api/budget';
import type { CommitRow, ImportField, ImportRow, NewCategoryProposal, Payee, PayeeSuggestion } from '../../api/imports';

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

const payeeKey = (name: string, income: boolean) => `${income ? '+' : '-'}${name.trim().toLowerCase()}`;

/** Empfänger ausgewählter neuer Umsätze ohne Kategorie, je Name und Richtung einmal (für den KI-Vorschlag) */
export function payeesWithoutCategory(rows: ImportRow[], choices: Record<string, Choice>): Payee[] {
  const payees = new Map<string, Payee>();
  for (const row of rows) {
    const choice = choices[row.key];
    if (row.status !== 'new' || !choice.selected || choice.category !== null || !row.counterparty.trim()) continue;
    payees.set(payeeKey(row.counterparty, row.amount > 0), { name: row.counterparty.trim(), income: row.amount > 0 });
  }
  return [...payees.values()];
}

/** KI-Vorschläge übernehmen, nur bei Umsätzen, die noch keine Kategorie haben. Gibt auch die Zahl gesetzter Umsätze zurück. */
export function applySuggestions(rows: ImportRow[], choices: Record<string, Choice>, suggestions: PayeeSuggestion[]) {
  const found = new Map(suggestions.filter((s) => s.category_id !== null).map((s) => [payeeKey(s.name, s.income), s.category_id!]));
  const next = { ...choices };
  let filled = 0;
  for (const row of rows) {
    const category = found.get(payeeKey(row.counterparty, row.amount > 0));
    if (row.status !== 'new' || category === undefined || next[row.key].category !== null) continue;
    next[row.key] = { ...next[row.key], category };
    filled += 1;
  }
  return { choices: next, filled };
}

/** Eine Kategorie allen Umsätzen dieser Empfänger geben, die noch keine haben (z.B. nach dem Anlegen) */
export function assignToPayees(rows: ImportRow[], choices: Record<string, Choice>, payees: Payee[], category: number) {
  return applySuggestions(rows, choices, payees.map((p) => ({ ...p, category_id: category, new_category: null })));
}

export type Proposal = NewCategoryProposal & { key: string; payees: Payee[]; rows: number };

/**
 * Vorgeschlagene neue Kategorien, gleiche (Hauptkategorie + Name) zusammengefasst, mit den Empfängern
 * und der Zahl ausgewählter Umsätze, die noch keine Kategorie haben. Ohne solche Umsätze entfällt der Vorschlag.
 */
export function proposalsFrom(suggestions: PayeeSuggestion[], rows: ImportRow[], choices: Record<string, Choice>): Proposal[] {
  const open = rows.filter((r) => r.status === 'new' && choices[r.key].selected && choices[r.key].category === null);
  const groups = new Map<string, Proposal>();
  for (const s of suggestions) {
    if (!s.new_category) continue;
    const count = open.filter((r) => payeeKey(r.counterparty, r.amount > 0) === payeeKey(s.name, s.income)).length;
    if (!count) continue;
    const key = `${s.new_category.parent_id}:${s.new_category.name.toLowerCase()}`;
    const group = groups.get(key) ?? { ...s.new_category, key, payees: [], rows: 0 };
    group.payees.push({ name: s.name, income: s.income });
    group.rows += count;
    groups.set(key, group);
  }
  return [...groups.values()].sort((a, b) => b.rows - a.rows);
}

// ─── GRUPPEN ───────────────────────────────────────────────────────────────────

export type Group = {
  key: string;
  name: string;
  income: boolean;
  rows: ImportRow[];
  /** Summe aller Umsätze der Gruppe (Ausgaben negativ) */
  total: number;
  selected: number;
  /** Ausgewählte Umsätze ohne Kategorie */
  missing: number;
  /** Gemeinsame Kategorie der ausgewählten Umsätze; null = keine, 'mixed' = verschiedene */
  category: number | null | 'mixed';
  source: ImportRow['category_source'];
  first: string;
  last: string;
};

export type GroupFilter = { direction: 'all' | 'expense' | 'income'; onlyMissing: boolean; sort: 'count' | 'amount' | 'name' };

const groupKey = (row: ImportRow) => payeeKey(row.counterparty.trim() || row.description, row.amount > 0);

/**
 * Neue Umsätze nach Empfänger und Richtung zusammengefasst, damit 1.600 Zeilen etwa 300 Entscheidungen werden.
 * Ohne Empfänger zählt die Beschreibung (z.B. "Kontoabschluss").
 */
export function groupRows(rows: ImportRow[], choices: Record<string, Choice>): Group[] {
  const groups = new Map<string, Group>();
  for (const row of rows) {
    if (row.status !== 'new') continue;
    const key = groupKey(row);
    const group = groups.get(key) ?? {
      key, name: row.counterparty.trim() || row.description, income: row.amount > 0, rows: [], total: 0,
      selected: 0, missing: 0, category: null, source: null, first: row.date, last: row.date,
    };
    group.rows.push(row);
    group.total += row.amount;
    if (row.date < group.first) group.first = row.date;
    if (row.date > group.last) group.last = row.date;
    groups.set(key, group);
  }
  for (const group of groups.values()) {
    const chosen = group.rows.filter((r) => choices[r.key].selected);
    group.selected = chosen.length;
    group.missing = chosen.filter((r) => choices[r.key].category === null).length;
    const categories = new Set(chosen.map((r) => choices[r.key].category));
    group.category = categories.size === 1 ? [...categories][0] : categories.size > 1 ? 'mixed' : null;
    group.source = chosen.find((r) => choices[r.key].category === r.category_id && r.category_source)?.category_source ?? null;
  }
  return [...groups.values()];
}

/** Sichtbare Gruppen nach Filter und Sortierung */
export function visibleGroups(groups: Group[], filter: GroupFilter) {
  const shown = groups.filter((g) => (filter.direction === 'all' || (filter.direction === 'income') === g.income)
    && (!filter.onlyMissing || g.missing > 0));
  const by = {
    count: (a: Group, b: Group) => b.rows.length - a.rows.length || a.name.localeCompare(b.name, 'de'),
    amount: (a: Group, b: Group) => Math.abs(b.total) - Math.abs(a.total),
    name: (a: Group, b: Group) => a.name.localeCompare(b.name, 'de'),
  }[filter.sort];
  return shown.sort(by);
}

/** Kategorie für alle ausgewählten Umsätze einer Gruppe */
export function setGroupCategory(group: Group, choices: Record<string, Choice>, category: number | null) {
  const next = { ...choices };
  for (const row of group.rows) {
    if (next[row.key].selected) next[row.key] = { ...next[row.key], category };
  }
  return next;
}

/** Alle Umsätze einer Gruppe aus- oder abwählen */
export function setGroupSelected(group: Group, choices: Record<string, Choice>, selected: boolean) {
  const next = { ...choices };
  for (const row of group.rows) next[row.key] = { ...next[row.key], selected };
  return next;
}

/**
 * "Rest zuordnen": alle ausgewählten neuen Umsätze ohne Kategorie bekommen je Richtung die gewählte
 * Kategorie (null = in dieser Richtung nichts ändern). Gibt auch die Zahl geänderter Umsätze zurück.
 */
export function assignRest(rows: ImportRow[], choices: Record<string, Choice>, expense: number | null, income: number | null) {
  const next = { ...choices };
  let filled = 0;
  for (const row of rows) {
    const category = row.amount > 0 ? income : expense;
    if (row.status !== 'new' || category === null || !next[row.key].selected || next[row.key].category !== null) continue;
    next[row.key] = { ...next[row.key], category };
    filled += 1;
  }
  return { choices: next, filled };
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
