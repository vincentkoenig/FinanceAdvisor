import { describe, expect, it } from 'vitest';
import type { Category } from '../../api/budget';
import type { Booking } from '../../api/overview';
import {
  counts, dayInMonth, daysForAverage, expensesByCategory, largestVariable, mainCategory, monthStart, monthTotals, sortBookings,
} from './model';

const OCT = new Date(2026, 9, 1, 12);
const OCT_30 = new Date(2026, 9, 30, 10);

const booking = (over: Partial<Booking>): Booking => ({
  id: 1, amount: 10, description: null, date: '2026-10-05', end_date: null, is_recurring: false, is_paused: false, paused_at: null,
  category_id: 2, category_name: 'Lebensmittel', category_type: 'variable_expense', ...over,
});

const categories: Category[] = [
  { id: 20, name: 'Lebenshaltung', type: 'variable_expense', parent_id: null },
  { id: 2, name: 'Lebensmittel', type: 'variable_expense', parent_id: 20 },
  { id: 5, name: 'Kino', type: 'variable_expense', parent_id: 21 },
  { id: 21, name: 'Freizeit', type: 'variable_expense', parent_id: null },
  { id: 3, name: 'Miete', type: 'fixed_expense', parent_id: null },
];

describe('Monat', () => {
  it('blättert vom heutigen Monat aus', () => {
    expect(monthStart(OCT_30, -1)).toEqual(new Date(2026, 8, 1, 12));
    expect(monthStart(OCT_30, 3)).toEqual(new Date(2027, 0, 1, 12));
  });

  it('zählt eine pausierte Buchung nur in Monaten vor der Pause', () => {
    const paused = booking({ is_recurring: true, is_paused: true, paused_at: '2026-11-03' });
    expect(counts(paused, OCT)).toBe(true);
    expect(counts(paused, new Date(2026, 10, 1, 12))).toBe(false);
    expect(counts(booking({ is_paused: true, paused_at: null }), OCT)).toBe(false);
  });

  it('summiert Einnahmen, Fixkosten und variable Ausgaben', () => {
    const totals = monthTotals([
      booking({ amount: 3000, category_type: 'income' }),
      booking({ amount: 1200, category_type: 'fixed_expense' }),
      booking({ amount: 80 }),
      booking({ amount: 999, is_recurring: true, is_paused: true, paused_at: '2026-10-10' }),
    ], OCT);
    expect(totals).toEqual({ income: 3000, fixed: 1200, variable: 80, left: 1720 });
  });

  it('teilt im laufenden Monat durch die Tage bis heute, sonst durch den ganzen Monat', () => {
    expect(daysForAverage(OCT, OCT_30)).toBe(30);
    expect(daysForAverage(new Date(2026, 1, 1, 12), OCT_30)).toBe(28);
  });
});

describe('Kategorien', () => {
  it('findet die Hauptkategorie einer Unterkategorie', () => {
    expect(mainCategory(2, categories)?.name).toBe('Lebenshaltung');
    expect(mainCategory(3, categories)?.name).toBe('Miete');
    expect(mainCategory(99, categories)).toBeNull();
  });

  it('fasst Ausgaben je Hauptkategorie zusammen, größte zuerst, ohne Einnahmen', () => {
    const rows = expensesByCategory([
      booking({ amount: 40, category_id: 2 }),
      booking({ amount: 25, category_id: 2 }),
      booking({ amount: 90, category_id: 5 }),
      booking({ amount: 3000, category_id: 1, category_type: 'income' }),
      booking({ amount: 7, category_id: undefined, category_name: null }),
    ], categories, OCT);
    expect(rows).toEqual([
      { label: 'Freizeit', value: 90 },
      { label: 'Lebenshaltung', value: 65 },
      { label: 'Ohne Kategorie', value: 7 },
    ]);
  });
});

describe('Buchungsliste', () => {
  it('setzt wiederkehrende Buchungen auf ihren Tag im gezeigten Monat', () => {
    const rent = booking({ is_recurring: true, date: '2026-01-31' });
    expect(dayInMonth(rent, OCT)).toBe('2026-10-31');
    expect(dayInMonth(rent, new Date(2026, 1, 1, 12))).toBe('2026-02-28');
    expect(dayInMonth(booking({ date: '2026-10-05' }), OCT)).toBe('2026-10-05');
  });

  it('sortiert die neuesten zuerst', () => {
    const list = sortBookings([
      booking({ id: 1, date: '2026-10-05' }),
      booking({ id: 2, date: '2025-03-20', is_recurring: true }),
      booking({ id: 3, date: '2026-10-28' }),
    ], OCT);
    expect(list.map((b) => b.id)).toEqual([3, 2, 1]);
  });

  it('nennt die größte variable Ausgabe', () => {
    expect(largestVariable([booking({ id: 1, amount: 20 }), booking({ id: 2, amount: 60 }), booking({ id: 3, amount: 900, category_type: 'fixed_expense' })], OCT)?.id).toBe(2);
    expect(largestVariable([], OCT)).toBeNull();
  });
});
