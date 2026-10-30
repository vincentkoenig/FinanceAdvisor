// Rechnungen des Haushaltsbuchs ohne React, damit sie sich einzeln testen lassen.
// Gleiche Regeln wie budget/service.py: eine pausierte wiederkehrende Buchung zählt nur in den
// Monaten, die vor ihrer Pause enden.
import type { Category } from '../../api/budget';
import type { Booking, BudgetSummary, CategoryType } from '../../api/overview';
import { isoDay, monthKey } from '../../lib/format';

/** Erster Tag des Monats, der `offset` Monate von heute entfernt ist */
export function monthStart(today: Date, offset: number) {
  return new Date(today.getFullYear(), today.getMonth() + offset, 1, 12);
}

function nextMonthKey(month: Date) {
  return isoDay(new Date(month.getFullYear(), month.getMonth() + 1, 1, 12));
}

/** Zählt die Buchung im Monat mit? Pausierte nur, wenn die Pause erst nach dem Monat begann */
export function counts(booking: Booking, month: Date) {
  if (!booking.is_paused) return true;
  return Boolean(booking.paused_at && booking.paused_at >= nextMonthKey(month));
}

export type MonthTotals = { income: number; fixed: number; variable: number; left: number };

export function monthTotals(bookings: Booking[], month: Date): MonthTotals {
  const sum = (type: CategoryType) => bookings
    .filter((b) => b.category_type === type && counts(b, month))
    .reduce((total, b) => total + b.amount, 0);
  const income = sum('income'), fixed = sum('fixed_expense'), variable = sum('variable_expense');
  return { income, fixed, variable, left: income - fixed - variable };
}

/** Im Format der Monatszusammenfassung, damit der Monatsfluss der Übersicht passt */
export function asSummary(totals: MonthTotals, cumulative: number): BudgetSummary {
  return {
    cumulative_balance: cumulative,
    current_month_balance: totals.left,
    current_month_income: totals.income,
    current_month_fixed: totals.fixed,
    current_month_variable: totals.variable,
  };
}

/** Hauptkategorie einer Buchung (Buchungen hängen meist an einer Unterkategorie) */
export function mainCategory(categoryId: number | undefined, categories: Category[]) {
  const own = categories.find((c) => c.id === categoryId);
  if (!own) return null;
  return own.parent_id === null ? own : categories.find((c) => c.id === own.parent_id) ?? own;
}

/** Ausgaben des Monats je Hauptkategorie, größte zuerst */
export function expensesByCategory(bookings: Booking[], categories: Category[], month: Date) {
  const totals = new Map<string, number>();
  for (const b of bookings) {
    if (b.category_type === 'income' || !counts(b, month)) continue;
    const label = mainCategory(b.category_id, categories)?.name ?? b.category_name ?? 'Ohne Kategorie';
    totals.set(label, (totals.get(label) ?? 0) + b.amount);
  }
  return [...totals].map(([label, value]) => ({ label, value })).sort((a, b) => b.value - a.value);
}

/** Tag, an dem die Buchung im Monat anfällt; wiederkehrende am Tag ihres Starts (höchstens Monatsende) */
export function dayInMonth(booking: Booking, month: Date) {
  if (!booking.is_recurring) return booking.date;
  const start = Number(booking.date.slice(8, 10));
  const last = new Date(month.getFullYear(), month.getMonth() + 1, 0).getDate();
  return `${monthKey(month)}-${String(Math.min(start, last)).padStart(2, '0')}`;
}

/** Neueste zuerst, wiederkehrende nach ihrem Tag im Monat */
export function sortBookings(bookings: Booking[], month: Date) {
  return [...bookings].sort((a, b) => dayInMonth(b, month).localeCompare(dayInMonth(a, month)) || b.id - a.id);
}

/** Größte variable Ausgabe für den Satz unter dem Titel */
export function largestVariable(bookings: Booking[], month: Date) {
  return bookings
    .filter((b) => b.category_type === 'variable_expense' && counts(b, month))
    .sort((a, b) => b.amount - a.amount)[0] ?? null;
}

/** Tage für den Tagesschnitt: im laufenden Monat bis heute, sonst der ganze Monat */
export function daysForAverage(month: Date, today: Date) {
  if (monthKey(month) === monthKey(today)) return today.getDate();
  return new Date(month.getFullYear(), month.getMonth() + 1, 0).getDate();
}
