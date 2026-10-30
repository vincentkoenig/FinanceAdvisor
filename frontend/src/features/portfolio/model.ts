// Rechnungen des Portfolios ohne React, damit sie sich einzeln testen lassen.
import type { Dividend, HistoryPoint, Trade } from '../../api/overview';
import { isoDay } from '../../lib/format';
import { changeSince, type PositionRow } from '../home/model';

export type Range = '1W' | '1M' | 'YTD' | '1J' | 'Max';

export const RANGES: { key: Range; words: string }[] = [
  { key: '1W', words: 'in einer Woche' },
  { key: '1M', words: 'in einem Monat' },
  { key: 'YTD', words: 'seit Jahresbeginn' },
  { key: '1J', words: 'in einem Jahr' },
  { key: 'Max', words: 'seit dem ersten Kauf' },
];

// Letzter Tag vor dem Zeitraum: sein Schlusswert ist der Ausgangspunkt
function rangeStart(range: Range, today: Date) {
  const y = today.getFullYear(), m = today.getMonth(), d = today.getDate();
  switch (range) {
    case '1W': return new Date(y, m, d - 7, 12);
    case '1M': return new Date(y, m - 1, d, 12);
    case 'YTD': return new Date(y - 1, 11, 31, 12);
    case '1J': return new Date(y - 1, m, d, 12);
    case 'Max': return null;
  }
}

/**
 * Wertverlauf im Zeitraum, beginnend mit dem letzten Tag davor. Der heutige Punkt trägt den
 * Depotwert zu Live-Kursen (der Verlauf schreibt für heute nur den letzten Schlusskurs fort).
 */
export function rangeSeries(history: HistoryPoint[], range: Range, today: Date, liveValue: number): HistoryPoint[] {
  if (history.length === 0) return [];
  const start = rangeStart(range, today);
  let from = 0;
  if (start) {
    const startKey = isoDay(start);
    from = Math.max(0, history.findLastIndex((point) => point.date <= startKey));
  }
  const todayKey = isoDay(today);
  const points = history.slice(from).filter((point) => point.date < todayKey);
  return [...points, { date: todayKey, value: liveValue }];
}

/** Kursbewegung im Zeitraum, ohne Käufe und Verkäufe; null mit weniger als zwei Punkten */
export function rangeChange(series: HistoryPoint[], trades: Trade[]) {
  if (series.length < 2) return null;
  return changeSince(series[0], series[series.length - 1].value, trades);
}

const TYPE_LABELS: Record<string, string> = { etf: 'ETFs', stock: 'Aktien', crypto: 'Krypto', metal: 'Edelmetalle' };

export type Slice = { key: string; label: string; value: number; share: number; color: string };

/** Depotwert nach Anlageart, größte zuerst; "Sonstige" immer zuletzt und in Grau */
export function allocation(rows: PositionRow[]): Slice[] {
  const total = rows.reduce((sum, row) => sum + row.value, 0);
  if (total <= 0) return [];
  const groups = new Map<string, number>();
  for (const row of rows) {
    const key = row.asset_type && TYPE_LABELS[row.asset_type] ? row.asset_type : 'other';
    groups.set(key, (groups.get(key) ?? 0) + row.value);
  }
  const sorted = [...groups].sort(([ka, a], [kb, b]) => Number(ka === 'other') - Number(kb === 'other') || b - a);
  return sorted.map(([key, value], i) => ({
    key,
    label: TYPE_LABELS[key] ?? 'Sonstige',
    value,
    share: (value / total) * 100,
    color: key === 'other' || i > 3 ? 'var(--chart-muted)' : `var(--share-${i + 1})`,
  }));
}

export type SortKey = 'name' | 'quantity' | 'price' | 'value' | 'gain';
export type Sort = { key: SortKey; dir: 1 | -1 };

export function sortRows(rows: PositionRow[], { key, dir }: Sort) {
  return [...rows].sort((a, b) => (key === 'name' ? a.name.localeCompare(b.name, 'de') : a[key] - b[key]) * dir);
}

/** Satz unter dem Titel: welche Position den Gewinn trägt, oder wo der Verlust herkommt */
export function finding(rows: PositionRow[]) {
  if (rows.length === 0) return null;
  const gain = rows.reduce((sum, row) => sum + row.gain, 0);
  const byGain = [...rows].sort((a, b) => b.gain - a.gain);
  return gain >= 0
    ? { kind: 'gain' as const, total: gain, top: byGain[0] }
    : { kind: 'loss' as const, total: gain, top: byGain[byGain.length - 1] };
}

/** Summe der Dividenden mit Ex-Tag im laufenden Jahr */
export function dividendsThisYear(dividends: Dividend[], today: Date) {
  const year = String(today.getFullYear());
  return dividends.filter((d) => d.ex_dividend_date.startsWith(year)).reduce((sum, d) => sum + d.total_amount, 0);
}

/** Runde Achsenwerte (Schritte 1, 2, 2,5 oder 5 × 10ⁿ), der oberste liegt über dem Höchstwert */
export function niceTicks(min: number, max: number, count = 4) {
  if (max === min) max = min + 1;
  const raw = (max - min) / count;
  const magnitude = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * magnitude).find((s) => s >= raw) ?? 10 * magnitude;
  const low = Math.floor(min / step) * step;
  let high = Math.ceil(max / step) * step;
  if (high <= max) high += step;
  const ticks: number[] = [];
  for (let v = low; v <= high + step / 2; v += step) ticks.push(Number(v.toFixed(10)));
  return ticks;
}
