// Rechnungen der Übersicht ohne React, damit sie sich einzeln testen lassen.
import type { Booking, BudgetSummary, HistoryPoint, Position, SavingsPlan, Trade } from '../../api/overview';
import { isoDay, monthKey } from '../../lib/format';

export type PortfolioTotals = { value: number; cost: number; gain: number; gainPct: number | null };

// Ohne Kurs zählt die Position mit dem Einstandspreis, wie im bisherigen Portfolio
export function portfolioTotals(positions: Position[]): PortfolioTotals {
  let value = 0;
  let cost = 0;
  for (const p of positions) {
    value += (p.current_price ?? p.avg_buy_price) * p.quantity;
    cost += p.avg_buy_price * p.quantity;
  }
  return { value, cost, gain: value - cost, gainPct: cost > 0 ? (value / cost - 1) * 100 : null };
}

/**
 * Veränderung des Depots seit gestern: heutiger Wert zu Live-Kursen gegen den letzten Tag
 * vor heute im Wertverlauf (der Verlauf schreibt für heute nur den letzten Schlusskurs fort).
 */
export function dayChange(history: HistoryPoint[], currentValue: number, trades: Trade[], today: Date) {
  const todayKey = isoDay(today);
  const before = [...history].reverse().find((point) => point.date < todayKey);
  return before ? changeSince(before, currentValue, trades) : null;
}

/**
 * Kursbewegung seit einem Punkt im Wertverlauf. Käufe und Verkäufe seitdem sind keine
 * Kursbewegung und werden herausgerechnet; Prozent bezogen auf den Wert plus Zukäufe.
 */
export function changeSince(start: HistoryPoint, currentValue: number, trades: Trade[]) {
  const netBought = trades
    .filter((t) => t.date > start.date)
    .reduce((sum, t) => sum + (t.type === 'buy' ? t.total : -t.total), 0);
  const abs = currentValue - start.value - netBought;
  const base = start.value + Math.max(netBought, 0);
  return { abs, pct: base > 0 ? (abs / base) * 100 : null };
}

export type PlanDate = { plan: SavingsPlan; date: Date };

// Gleiche Regel wie die API: Stichtag ist der Tag im Monat, höchstens der 28.
export function planDates(plans: SavingsPlan[], today: Date) {
  const due: PlanDate[] = [];
  const upcoming: PlanDate[] = [];
  for (const plan of plans) {
    const day = Math.min(plan.day_of_month, 28);
    const thisMonth = new Date(today.getFullYear(), today.getMonth(), day, 12);
    if (plan.is_due) due.push({ plan, date: thisMonth });
    else if (today.getDate() < day) upcoming.push({ plan, date: thisMonth });
    else upcoming.push({ plan, date: new Date(today.getFullYear(), today.getMonth() + 1, day, 12) });
  }
  upcoming.sort((a, b) => a.date.getTime() - b.date.getTime());
  return { due, upcoming };
}

export type FlowPart = { key: 'fixed' | 'variable' | 'invested' | 'free'; label: string; short: string; value: number };

// Wohin das Einkommen des Monats geht. Sparpläne, die diesen Monat ausgeführt wurden,
// werden aus dem freien Rest herausgerechnet (sie sind keine Buchung im Haushaltsbuch).
export function monthFlow(summary: BudgetSummary, plans: SavingsPlan[], today: Date) {
  const income = summary.current_month_income;
  const left = summary.current_month_balance;
  const key = monthKey(today);
  const executed = plans.filter((p) => p.last_executed?.startsWith(key)).reduce((s, p) => s + p.amount, 0);
  const invested = Math.min(executed, Math.max(left, 0));
  const parts: FlowPart[] = [
    { key: 'fixed', label: 'Fixkosten', short: 'Fixkosten', value: summary.current_month_fixed },
    { key: 'variable', label: 'Variable Ausgaben', short: 'Variabel', value: summary.current_month_variable },
    { key: 'invested', label: 'Investiert per Sparplan', short: 'Sparplan', value: invested },
    { key: 'free', label: 'Frei übrig', short: 'Frei', value: Math.max(left - invested, 0) },
  ];
  // Der Balken zeigt Anteile am Einkommen; gibt es keins oder mehr Ausgaben als Einnahmen, passt das nicht
  return { income, left, parts, drawable: income > 0 && left >= 0 };
}

/** Vorzeichen einer Buchung: Einnahmen positiv, Ausgaben negativ */
export function signedAmount(booking: Booking) {
  return booking.category_type === 'income' ? booking.amount : -booking.amount;
}

/** Die neuesten Buchungen (die API liefert sie schon absteigend nach Datum) */
export function recentBookings(bookings: Booking[], count = 4) {
  return [...bookings].sort((a, b) => b.date.localeCompare(a.date) || b.id - a.id).slice(0, count);
}

export type PositionRow = Position & { price: number; value: number; cost: number; gain: number; gainPct: number | null };

/** Positionen mit Wert, Einstand und Gewinn seit Kauf (ohne Kurs zählt der Einstandspreis) */
export function positionRows(positions: Position[]): PositionRow[] {
  return positions.map((p) => {
    const price = p.current_price ?? p.avg_buy_price;
    const value = price * p.quantity;
    const cost = p.avg_buy_price * p.quantity;
    return { ...p, price, value, cost, gain: value - cost, gainPct: cost > 0 ? (value / cost - 1) * 100 : null };
  });
}

/** Die größten Positionen nach aktuellem Wert */
export function largestPositions(positions: Position[], count = 4) {
  return positionRows(positions).sort((a, b) => b.value - a.value).slice(0, count);
}

/** Kurzzeichen für den runden Platzhalter einer Position */
export function token(symbol: string, name: string) {
  const base = symbol && symbol !== '-' ? symbol.split(/[.\-=]/)[0] : name;
  return base.replace(/[^A-Za-z0-9]/g, '').slice(0, 4).toUpperCase();
}
