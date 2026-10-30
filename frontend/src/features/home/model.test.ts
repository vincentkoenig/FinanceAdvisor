import { describe, expect, it } from 'vitest';
import type { Booking, BudgetSummary, Position, SavingsPlan, Trade } from '../../api/overview';
import { eur, parseAmount, pct } from '../../lib/format';
import { dayChange, largestPositions, monthFlow, planDates, portfolioTotals, recentBookings, token } from './model';

const position = (over: Partial<Position>): Position =>
  ({ asset_id: 1, name: 'X', symbol: 'X', quantity: 1, avg_buy_price: 10, current_price: 10, ...over });

const plan = (over: Partial<SavingsPlan>): SavingsPlan =>
  ({ id: 1, asset_id: 1, asset_name: 'X', asset_symbol: 'X', amount: 100, day_of_month: 1, last_executed: null, is_due: false, ...over });

const summary = (over: Partial<BudgetSummary> = {}): BudgetSummary => ({
  cumulative_balance: 0, current_month_balance: 1000, current_month_income: 3000,
  current_month_fixed: 1200, current_month_variable: 800, ...over,
});

const OCT_30 = new Date(2026, 9, 30, 10);

describe('Formatierung', () => {
  it('schreibt Euro und Prozent deutsch mit echtem Minuszeichen', () => {
    expect(eur(1234.5)).toBe('1.234,50 €');
    expect(eur(-3.2)).toBe('−3,20 €');
    expect(eur(200, { sign: true })).toBe('+200,00 €');
    expect(eur(-0.001, { sign: true })).toBe('0,00 €');
    expect(eur(1234.5, { digits: 0 })).toBe('1.235 €');
    expect(pct(7.69)).toBe('+7,7 %');
    expect(pct(-20)).toBe('−20,0 %');
  });

  it('liest Beträge mit Komma, Punkt oder Euro-Zeichen', () => {
    expect(parseAmount('')).toBeNull();
    expect(parseAmount('500')).toBe(500);
    expect(parseAmount('250,50 €')).toBe(250.5);
    expect(parseAmount('1.250,5')).toBe(1250.5);
    expect(parseAmount('12.5')).toBe(12.5);
    expect(parseAmount('zwölf')).toBeNaN();
  });
});

describe('Depot', () => {
  it('summiert Wert, Einstand und Gewinn; ohne Kurs zählt der Einstandspreis', () => {
    const totals = portfolioTotals([
      position({ quantity: 100, avg_buy_price: 80, current_price: 100 }),
      position({ quantity: 2, avg_buy_price: 50, current_price: null }),
    ]);
    expect(totals).toEqual({ value: 10100, cost: 8100, gain: 2000, gainPct: expect.closeTo(24.69, 2) });
  });

  it('hat ohne Positionen keinen Prozentwert', () => {
    expect(portfolioTotals([]).gainPct).toBeNull();
  });

  it('vergleicht den heutigen Wert mit dem letzten Tag vor heute', () => {
    const history = [{ date: '2026-10-28', value: 13800 }, { date: '2026-10-29', value: 13900 }, { date: '2026-10-30', value: 13900 }];
    expect(dayChange(history, 14000, [], OCT_30)).toEqual({ abs: 100, pct: expect.closeTo(0.719, 2) });
    // Verlauf erst seit heute: kein Vortag
    expect(dayChange([{ date: '2026-10-30', value: 100 }], 120, [], OCT_30)).toBeNull();
  });

  it('zählt einen Kauf von heute nicht als Kursgewinn', () => {
    const history = [{ date: '2026-10-29', value: 10000 }];
    const trade = (type: 'buy' | 'sell', total: number, date: string) =>
      ({ id: 1, asset_id: 1, type, quantity: 1, price: total, total, date }) as Trade;
    // 200 € gekauft, Depot jetzt 10.250 €: nur 50 € sind Kursbewegung
    expect(dayChange(history, 10250, [trade('buy', 200, '2026-10-30'), trade('buy', 999, '2026-10-29')], OCT_30)!.abs).toBe(50);
    expect(dayChange(history, 9800, [trade('sell', 300, '2026-10-30')], OCT_30)!.abs).toBe(100);
  });

  it('ordnet die Positionen nach Wert', () => {
    const list = largestPositions([
      position({ asset_id: 1, quantity: 1, current_price: 10 }),
      position({ asset_id: 2, quantity: 1, current_price: 30 }),
    ]);
    expect(list.map((p) => p.asset_id)).toEqual([2, 1]);
    expect(list[0].gain).toBe(20);
  });

  it('kürzt Symbole für den runden Platzhalter', () => {
    expect(token('EUNL.DE', 'iShares')).toBe('EUNL');
    expect(token('BTC-EUR', 'Bitcoin')).toBe('BTC');
    expect(token('-', 'Gold')).toBe('GOLD');
  });
});

describe('Sparpläne', () => {
  it('trennt Fälliges von Geplantem und nennt den nächsten Termin', () => {
    const { due, upcoming } = planDates([
      plan({ id: 1, is_due: true, day_of_month: 1 }),
      plan({ id: 2, day_of_month: 15, last_executed: '2026-10-15' }),
      plan({ id: 3, day_of_month: 31 }),
    ], OCT_30);
    expect(due.map((d) => [d.plan.id, d.date.getDate(), d.date.getMonth()])).toEqual([[1, 1, 9]]);
    // Tag 31 zählt wie in der API als 28.; schon vorbei, also nächster Monat
    expect(upcoming.map((d) => [d.plan.id, d.date.getDate(), d.date.getMonth()])).toEqual([[2, 15, 10], [3, 28, 10]]);
  });
});

describe('Monatsfluss', () => {
  it('rechnet diesen Monat ausgeführte Sparpläne aus dem freien Rest heraus', () => {
    const flow = monthFlow(summary(), [plan({ amount: 50, last_executed: '2026-10-15' }), plan({ amount: 99, last_executed: '2026-09-01' })], OCT_30);
    expect(flow.parts.map((p) => [p.key, p.value])).toEqual([['fixed', 1200], ['variable', 800], ['invested', 50], ['free', 950]]);
    // Die Teile ergeben zusammen das Einkommen
    expect(flow.parts.reduce((s, p) => s + p.value, 0)).toBe(flow.income);
    expect(flow.drawable).toBe(true);
  });

  it('zeichnet keinen Balken, wenn die Ausgaben die Einnahmen übersteigen', () => {
    const flow = monthFlow(summary({ current_month_balance: -200, current_month_variable: 2000 }), [plan({ last_executed: '2026-10-01' })], OCT_30);
    expect(flow.drawable).toBe(false);
    expect(flow.parts.find((p) => p.key === 'invested')!.value).toBe(0);
  });
});

describe('Buchungen', () => {
  it('nimmt die neuesten zuerst', () => {
    const b = (id: number, date: string) => ({ id, date }) as Booking;
    expect(recentBookings([b(1, '2026-10-01'), b(2, '2026-10-28'), b(3, '2026-10-28')], 2).map((x) => x.id)).toEqual([3, 2]);
  });
});
