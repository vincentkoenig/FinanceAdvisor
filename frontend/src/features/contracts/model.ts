// Texte und Gruppierung der Verträge-Seite. Die Fristen selbst kommen fertig vom Server.
import type { Category } from '../../api/budget';
import type { Contract, ContractCategory, ContractInput, NoticeUnit, PaymentInterval } from '../../api/contracts';
import type { Booking } from '../../api/overview';
import { parseDay } from '../../lib/format';

export const CATEGORIES: { value: ContractCategory; label: string }[] = [
  { value: 'insurance', label: 'Versicherungen' },
  { value: 'energy', label: 'Strom & Gas' },
  { value: 'telecom', label: 'Handy & Internet' },
  { value: 'subscription', label: 'Abos & Streaming' },
  { value: 'fitness', label: 'Fitness' },
  { value: 'loan', label: 'Kredite' },
  { value: 'other', label: 'Sonstiges' },
];

export const INTERVALS: { value: PaymentInterval; label: string; perYear: number }[] = [
  { value: 'monthly', label: 'monatlich', perYear: 12 },
  { value: 'quarterly', label: 'vierteljährlich', perYear: 4 },
  { value: 'half_yearly', label: 'halbjährlich', perYear: 2 },
  { value: 'yearly', label: 'jährlich', perYear: 1 },
];

export const NOTICE_UNITS: { value: NoticeUnit; label: string }[] = [
  { value: 'days', label: 'Tage' },
  { value: 'weeks', label: 'Wochen' },
  { value: 'months', label: 'Monate' },
];

/** Verlängerung in Monaten; null = keine, der Vertrag endet nach der ersten Laufzeit */
export const RENEWALS: { value: number | null; label: string }[] = [
  { value: 1, label: 'jeden Monat' },
  { value: 3, label: 'alle 3 Monate' },
  { value: 6, label: 'alle 6 Monate' },
  { value: 12, label: 'jedes Jahr' },
  { value: 24, label: 'alle 2 Jahre' },
  { value: null, label: 'gar nicht, endet von selbst' },
];

type Terms = Pick<ContractInput, 'interval' | 'min_term_months' | 'renewal_months' | 'notice_value' | 'notice_unit'>;

/** Übliche Bedingungen je Art, als Vorschlag beim Anlegen (alles bleibt änderbar) */
export const TYPICAL_TERMS: Record<ContractCategory, Terms> = {
  insurance: { interval: 'yearly', min_term_months: null, renewal_months: 12, notice_value: 3, notice_unit: 'months' },
  energy: { interval: 'monthly', min_term_months: 12, renewal_months: 1, notice_value: 1, notice_unit: 'months' },
  telecom: { interval: 'monthly', min_term_months: 24, renewal_months: 1, notice_value: 1, notice_unit: 'months' },
  subscription: { interval: 'monthly', min_term_months: null, renewal_months: 1, notice_value: 0, notice_unit: 'days' },
  fitness: { interval: 'monthly', min_term_months: 12, renewal_months: 1, notice_value: 1, notice_unit: 'months' },
  loan: { interval: 'monthly', min_term_months: 60, renewal_months: null, notice_value: 0, notice_unit: 'days' },
  other: { interval: 'monthly', min_term_months: null, renewal_months: 12, notice_value: 3, notice_unit: 'months' },
};

/** Ab so vielen Tagen bis zum Kündigungstag gilt ein Vertrag als "bald kündbar" */
export const SOON_DAYS = 60;

export const categoryLabel = (value: ContractCategory) => CATEGORIES.find((c) => c.value === value)!.label;
export const intervalLabel = (value: PaymentInterval) => INTERVALS.find((i) => i.value === value)!.label;

/** "2026-09-30" → "30.09.2026" */
export const dateLong = (iso: string) => parseDay(iso).toLocaleDateString('de-DE', { day: '2-digit', month: '2-digit', year: 'numeric' });

export function inDays(days: number) {
  if (days === 0) return 'heute';
  if (days === 1) return 'morgen';
  return `in ${days} Tagen`;
}

/** Monatlich verlängert und nicht mehr in der Mindestlaufzeit: jeden Monat kündbar, keine Frist zum Verpassen */
export const monthlyCancellable = (c: Contract) =>
  c.renewal_months === 1 && c.cancel_effective !== null && c.cancel_effective !== c.min_term_end;

/** Hat eine Frist, die man verpassen kann */
export const hasDeadline = (c: Contract) => c.cancel_by !== null && !monthlyCancellable(c);

/** Verträge, deren Kündigungstag in den nächsten SOON_DAYS Tagen liegt, die nächste Frist zuerst */
export const soonCancellable = (contracts: Contract[]) =>
  contracts.filter((c) => hasDeadline(c) && c.days_to_cancel! <= SOON_DAYS)
    .sort((a, b) => a.days_to_cancel! - b.days_to_cancel!);

/** Nach Art gruppiert in fester Reihenfolge; innerhalb einer Art bleibt die Sortierung des Servers (nach Frist) */
export function byCategory(contracts: Contract[]) {
  return CATEGORIES
    .map(({ value, label }) => ({ category: value, label, contracts: contracts.filter((c) => c.category === value) }))
    .filter((group) => group.contracts.length > 0);
}

/** Zweite Zeile eines Vertrags: wann kündbar oder wann er endet */
export function deadlineText(contract: Contract) {
  switch (contract.status) {
    case 'cancelled':
      return `gekündigt, endet am ${dateLong(contract.ends_on!)}`;
    case 'ending':
      return contract.ends_on ? `endet am ${dateLong(contract.ends_on)} von selbst` : 'endet von selbst';
    case 'ended':
      return contract.ends_on ? `beendet seit ${dateLong(contract.ends_on)}` : 'beendet';
    default:
      if (monthlyCancellable(contract)) return `monatlich kündbar, frühestens zum ${dateLong(contract.cancel_effective!)}`;
      return contract.cancel_by
        ? `kündbar bis ${dateLong(contract.cancel_by)} zum ${dateLong(contract.cancel_effective!)}`
        : 'keine Kündigungsfrist';
  }
}

export const STATUS_PILL: Partial<Record<Contract['status'], string>> = {
  cancelled: 'gekündigt',
  ending: 'läuft aus',
  ended: 'beendet',
};

/** Beitrag anteilig pro Monat, wie er im Haushaltsbuch landet (null bei ungültigem Betrag) */
export function monthlyShare(amount: number | null, interval: PaymentInterval) {
  if (amount === null || Number.isNaN(amount) || amount <= 0) return null;
  const perYear = INTERVALS.find((i) => i.value === interval)!.perYear;
  return Math.round(((amount * perYear) / 12) * 100) / 100;
}

/**
 * Wohin ein Vertrag im Haushaltsbuch kann: Fixkosten-Kategorien für eine neue Buchung (Unterkategorien,
 * eine Hauptkategorie ohne Unterkategorien selbst) und wiederkehrende Fixkosten-Buchungen, die noch
 * zu keinem Vertrag gehören.
 */
export function bookingChoices(categories: Category[], bookings: Booking[], contracts: Contract[]) {
  const fixed = categories.filter((c) => c.type === 'fixed_expense');
  const mains = fixed.filter((c) => c.parent_id === null);
  const leaves = mains.flatMap((main) => {
    const subs = fixed.filter((c) => c.parent_id === main.id);
    return subs.length
      ? subs.map((sub) => ({ id: sub.id, name: sub.name, label: `${main.name} · ${sub.name}` }))
      : [{ id: main.id, name: main.name, label: main.name }];
  });
  const linked = new Set(contracts.map((c) => c.booking?.id).filter(Boolean));
  const free = bookings
    .filter((b) => b.is_recurring && b.category_type === 'fixed_expense' && !linked.has(b.id))
    .map((b) => ({ id: b.id, label: b.description || b.category_name || 'Buchung', amount: b.amount }));
  return { categories: leaves, bookings: free };
}

// Wörter, an denen eine passende Fixkosten-Kategorie je Art zu erkennen ist (wie die Standardkategorien)
const KIND_WORDS: Record<ContractCategory, string[]> = {
  insurance: ['versicherung'],
  energy: ['strom', 'gas', 'nebenkosten'],
  telecom: ['handy', 'internet', 'telefon'],
  subscription: ['streaming', 'abo'],
  fitness: ['fitness', 'sport'],
  loan: ['kredit', 'leasing', 'darlehen'],
  other: ['verträge'],
};

/**
 * Vorschlag für die Kategorie einer neuen Buchung: zuerst eine, deren Name im Vertragsnamen steckt
 * ("KFZ" in "Kfz-Versicherung"), dann eine, die zur Art passt, dann eine unter "… Verträge", sonst die erste.
 */
export function suggestCategory(leaves: { id: number; name: string; label: string }[], contractName: string, kind: ContractCategory) {
  const name = contractName.toLowerCase();
  const label = (leaf: { label: string }) => leaf.label.toLowerCase();
  return leaves.find((leaf) => leaf.name.length >= 3 && name.includes(leaf.name.toLowerCase()))
    ?? leaves.find((leaf) => KIND_WORDS[kind].some((word) => label(leaf).includes(word)))
    ?? leaves.find((leaf) => label(leaf).includes('verträge'))
    ?? leaves[0];
}

// Ausgeblendete Vorschläge (Schlüssel der Abbuchung). Nur eine Bequemlichkeit dieses Browsers:
// ohne Speicher (privates Fenster) erscheinen sie eben wieder.
const DISMISSED_KEY = 'fintrack.contracts.dismissed';

export function readDismissed(): string[] {
  try {
    const value = JSON.parse(localStorage.getItem(DISMISSED_KEY) ?? '[]');
    return Array.isArray(value) ? value.filter((v) => typeof v === 'string') : [];
  } catch {
    return [];
  }
}

export function saveDismissed(keys: string[]) {
  try {
    localStorage.setItem(DISMISSED_KEY, JSON.stringify(keys));
  } catch {
    // Speicher nicht verfügbar: dann nur bis zum Neuladen ausgeblendet
  }
}
