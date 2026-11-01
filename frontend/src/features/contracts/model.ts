// Texte und Gruppierung der Verträge-Seite. Die Fristen selbst kommen fertig vom Server.
import type { Contract, ContractCategory, ContractInput, NoticeUnit, PaymentInterval } from '../../api/contracts';
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

export const INTERVALS: { value: PaymentInterval; label: string; per: string }[] = [
  { value: 'monthly', label: 'monatlich', per: 'Monat' },
  { value: 'quarterly', label: 'vierteljährlich', per: 'Quartal' },
  { value: 'half_yearly', label: 'halbjährlich', per: 'Halbjahr' },
  { value: 'yearly', label: 'jährlich', per: 'Jahr' },
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
