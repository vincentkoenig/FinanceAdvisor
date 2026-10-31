import { describe, expect, it } from 'vitest';
import type { Dividend, Position, Trade } from '../../api/overview';
import { positionRows } from '../home/model';
import { allocation, dividendsThisYear, finding, niceTicks, rangeChange, rangeSeries, sortRows, tradeMarks } from './model';

const OCT_30 = new Date(2026, 9, 30, 10);

const position = (over: Partial<Position>): Position =>
  ({ asset_id: 1, name: 'X', symbol: 'X', asset_type: 'etf', quantity: 1, avg_buy_price: 10, current_price: 10, ...over });

const history = [
  { date: '2025-12-30', value: 900 },
  { date: '2025-12-31', value: 950 },
  { date: '2026-09-29', value: 990 },
  { date: '2026-10-01', value: 1000 },
  { date: '2026-10-29', value: 1100 },
  { date: '2026-10-30', value: 1100 },
];

describe('Wertverlauf', () => {
  it('beginnt mit dem letzten Tag vor dem Zeitraum und endet mit dem Live-Wert', () => {
    const month = rangeSeries(history, '1M', OCT_30, 1150);
    expect(month.map((p) => p.date)).toEqual(['2026-09-29', '2026-10-01', '2026-10-29', '2026-10-30']);
    expect(month.at(-1)!.value).toBe(1150);
    expect(rangeSeries(history, 'YTD', OCT_30, 1150)[0].date).toBe('2025-12-31');
    expect(rangeSeries(history, 'Max', OCT_30, 1150)).toHaveLength(6);
    // Verlauf jünger als der Zeitraum: alles, was da ist
    expect(rangeSeries(history.slice(3), '1J', OCT_30, 1150)[0].date).toBe('2026-10-01');
    expect(rangeSeries([], '1M', OCT_30, 0)).toEqual([]);
  });

  it('rechnet Käufe im Zeitraum aus der Entwicklung heraus', () => {
    const series = rangeSeries(history, '1W', OCT_30, 1300);
    const buy = { id: 1, asset_id: 1, asset_name: 'X', asset_symbol: 'X', type: 'buy', quantity: 1, price: 100, total: 100, date: '2026-10-30' } as Trade;
    // 1.000 € am 23.10. fortgeschrieben (letzter Punkt davor: 1. Okt.), jetzt 1.300 €, davon 100 € gekauft
    expect(series[0]).toEqual({ date: '2026-10-01', value: 1000 });
    expect(rangeChange(series, [buy])).toEqual({ abs: 200, pct: expect.closeTo(18.18, 2) });
    expect(rangeChange([{ date: '2026-10-30', value: 5 }], [])).toBeNull();
  });

  it('wählt runde Achsenwerte über dem Höchstwert', () => {
    expect(niceTicks(9700, 14000)).toEqual([8000, 10000, 12000, 14000, 16000]);
    expect(niceTicks(0, 100)).toEqual([0, 25, 50, 75, 100, 125]);
  });
});

describe('Aufteilung', () => {
  it('gruppiert nach Anlageart, größte zuerst, Sonstige zuletzt in Grau', () => {
    const slices = allocation(positionRows([
      position({ asset_id: 1, asset_type: 'etf', quantity: 60 }),
      position({ asset_id: 2, asset_type: 'crypto', quantity: 10 }),
      position({ asset_id: 3, asset_type: 'etf', quantity: 10 }),
      position({ asset_id: 4, asset_type: null, quantity: 20 }),
    ]));
    expect(slices.map((s) => [s.label, s.value, Math.round(s.share), s.color])).toEqual([
      ['ETFs', 700, 70, 'var(--share-1)'],
      ['Krypto', 100, 10, 'var(--share-2)'],
      ['Sonstige', 200, 20, 'var(--chart-muted)'],
    ]);
    expect(allocation([])).toEqual([]);
  });
});

describe('Positionen', () => {
  const rows = positionRows([
    position({ asset_id: 1, name: 'Bitcoin', quantity: 1, avg_buy_price: 50, current_price: 40 }),
    position({ asset_id: 2, name: 'Apple', quantity: 2, avg_buy_price: 10, current_price: 30 }),
  ]);

  it('sortiert nach Spalte und Richtung', () => {
    expect(sortRows(rows, { key: 'value', dir: -1 }).map((r) => r.asset_id)).toEqual([2, 1]);
    expect(sortRows(rows, { key: 'name', dir: 1 }).map((r) => r.name)).toEqual(['Apple', 'Bitcoin']);
    expect(sortRows(rows, { key: 'gain', dir: 1 }).map((r) => r.asset_id)).toEqual([1, 2]);
  });

  it('nennt den größten Gewinnbringer oder die größte Verlustposition', () => {
    expect(finding(rows)).toMatchObject({ kind: 'gain', total: 30, top: { name: 'Apple' } });
    const losing = positionRows([position({ name: 'A', current_price: 5 }), position({ name: 'B', current_price: 8 })]);
    expect(finding(losing)).toMatchObject({ kind: 'loss', total: -7, top: { name: 'A' } });
    expect(finding([])).toBeNull();
  });
});

describe('Dividenden', () => {
  it('summiert nur das laufende Jahr', () => {
    const d = (date: string, total: number) => ({ ex_dividend_date: date, total_amount: total }) as Dividend;
    expect(dividendsThisYear([d('2026-03-01', 10), d('2026-09-01', 5.5), d('2025-12-01', 99)], OCT_30)).toBe(15.5);
  });
});

describe('tradeMarks', () => {
  const series = [
    { date: '2026-10-02', value: 100 },
    { date: '2026-10-05', value: 110 },
    { date: '2026-10-06', value: 120 },
    { date: '2026-10-30', value: 130 },
  ];
  const trade = (id: number, date: string, type: 'buy' | 'sell' = 'buy'): Trade =>
    ({ id, asset_id: 1, asset_name: 'X', asset_symbol: 'X', type, quantity: 1, price: 10, total: 10, date });

  it('setzt jeden Handel auf den ersten Punkt ab seinem Tag und fasst Tage zusammen', () => {
    const marks = tradeMarks(series, [
      trade(1, '2026-10-04'), trade(2, '2026-10-05', 'sell'), trade(3, '2026-10-06T09:30:00'), trade(4, '2026-10-30'),
    ]);
    expect(marks.map((m) => [m.index, m.trades.map((t) => t.id)])).toEqual([[1, [1, 2]], [2, [3]], [3, [4]]]);
  });

  it('lässt Käufe vor oder am Ausgangstag und nach dem letzten Punkt weg', () => {
    expect(tradeMarks(series, [trade(1, '2026-09-01'), trade(2, '2026-10-02'), trade(3, '2026-11-01')])).toEqual([]);
  });
});
