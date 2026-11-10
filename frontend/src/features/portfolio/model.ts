// Rechnungen des Portfolios ohne React, damit sie sich einzeln testen lassen.
import type { Dividend, HistoryPoint, PerformancePoint, Trade } from '../../api/overview';
import { isoDay, parseDay } from '../../lib/format';
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
export function rangeStart(range: Range, today: Date) {
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

export type ReturnPoint = { date: string; portfolio: number; benchmark: number | null };

/**
 * Rendite im Zeitraum in Prozent, Depot und Index ab demselben Ausgangstag bei 0. Hat der Index im
 * Zeitraum Kurse, beginnt der Vergleich am ersten Tag mit Indexkurs, damit beide dieselbe Strecke
 * messen. Ohne Indexkurs bleibt benchmark überall null.
 */
export function returnSeries(points: PerformancePoint[], range: Range, today: Date): ReturnPoint[] {
  if (points.length === 0) return [];
  const start = rangeStart(range, today);
  let from = 0;
  if (start) {
    const startKey = isoDay(start);
    from = Math.max(0, points.findLastIndex((point) => point.date <= startKey));
  }
  let slice = points.slice(from);
  const firstBench = slice.findIndex((point) => point.benchmark !== null);
  if (firstBench > 0) slice = slice.slice(firstBench);
  const base = slice[0];
  return slice.map((point) => ({
    date: point.date,
    portfolio: (point.portfolio / base.portfolio - 1) * 100,
    benchmark: base.benchmark !== null && point.benchmark !== null ? (point.benchmark / base.benchmark - 1) * 100 : null,
  }));
}

export type ReturnStats = {
  /** Rendite im Zeitraum, in Prozent */
  total: number;
  /** Rendite pro Jahr; null bei weniger als einem Jahr, weil sie dann nur hochgerechnet wäre */
  perYear: number | null;
  /** Schwankung (Standardabweichung der Tagesrenditen an Werktagen, aufs Jahr gerechnet) */
  volatility: number | null;
  /** Größter Rückgang von einem Höchststand, in Prozent (≤ 0) */
  drawdown: number;
};

/** Kennzahlen einer Renditekurve (Prozentwerte ab 0, wie aus returnSeries) */
export function returnStats(dates: string[], percents: number[]): ReturnStats | null {
  if (percents.length < 2) return null;
  const factors = percents.map((p) => 1 + p / 100);
  const total = (factors[factors.length - 1] / factors[0] - 1) * 100;
  const days = (parseDay(dates[dates.length - 1]).getTime() - parseDay(dates[0]).getTime()) / 86_400_000;
  const perYear = days >= 365 ? ((factors[factors.length - 1] / factors[0]) ** (365 / days) - 1) * 100 : null;

  // Wochenenden tragen keine Kursbewegung und würden die Schwankung kleiner rechnen
  const daily: number[] = [];
  for (let i = 1; i < factors.length; i++) {
    const weekday = parseDay(dates[i]).getDay();
    if (weekday !== 0 && weekday !== 6) daily.push(factors[i] / factors[i - 1] - 1);
  }
  let volatility: number | null = null;
  if (daily.length >= 5) {
    const mean = daily.reduce((sum, r) => sum + r, 0) / daily.length;
    const variance = daily.reduce((sum, r) => sum + (r - mean) ** 2, 0) / (daily.length - 1);
    volatility = Math.sqrt(variance * 252) * 100;
  }

  let peak = factors[0], drawdown = 0;
  for (const f of factors) {
    peak = Math.max(peak, f);
    drawdown = Math.min(drawdown, (f / peak - 1) * 100);
  }
  return { total, perYear, volatility, drawdown };
}

export type Tile<T> = { item: T; x: number; y: number; w: number; h: number };

/**
 * Kacheln für die Heatmap (squarified treemap): Fläche im Verhältnis zum Gewicht, möglichst
 * quadratisch, größte oben links. Gewichte ≤ 0 fallen weg.
 */
export function squarify<T>(items: { item: T; weight: number }[], width: number, height: number): Tile<T>[] {
  const total = items.reduce((sum, i) => sum + Math.max(0, i.weight), 0);
  if (total <= 0 || width <= 0 || height <= 0) return [];
  const scaled = items.filter((i) => i.weight > 0).sort((a, b) => b.weight - a.weight)
    .map((i) => ({ item: i.item, area: (i.weight / total) * width * height }));

  const out: Tile<T>[] = [];
  let rect = { x: 0, y: 0, w: width, h: height };
  const worst = (row: typeof scaled, side: number) => {
    const sum = row.reduce((s, r) => s + r.area, 0);
    const max = Math.max(...row.map((r) => r.area)), min = Math.min(...row.map((r) => r.area));
    return Math.max((side * side * max) / (sum * sum), (sum * sum) / (side * side * min));
  };
  const place = (row: typeof scaled) => {
    const sum = row.reduce((s, r) => s + r.area, 0);
    if (rect.w >= rect.h) {
      const w = sum / rect.h;
      let y = rect.y;
      for (const r of row) { const h = r.area / w; out.push({ item: r.item, x: rect.x, y, w, h }); y += h; }
      rect = { x: rect.x + w, y: rect.y, w: rect.w - w, h: rect.h };
    } else {
      const h = sum / rect.w;
      let x = rect.x;
      for (const r of row) { const w = r.area / h; out.push({ item: r.item, x, y: rect.y, w, h }); x += w; }
      rect = { x: rect.x, y: rect.y + h, w: rect.w, h: rect.h - h };
    }
  };

  let row: typeof scaled = [];
  for (let i = 0; i < scaled.length;) {
    const side = Math.min(rect.w, rect.h);
    if (row.length === 0 || worst([...row, scaled[i]], side) <= worst(row, side)) row.push(scaled[i++]);
    else { place(row); row = []; }
  }
  if (row.length) place(row);
  return out;
}

export type TradeMark = { index: number; trades: Trade[] };

/**
 * Käufe und Verkäufe im Zeitraum als Markierungen auf dem Wertverlauf: jeder auf dem ersten Punkt, in
 * dem er im Wert steckt (erster Punkt am oder nach dem Handelstag, z. B. Montag für einen Kauf am
 * Samstag). Der erste Punkt ist der Tag vor dem Zeitraum, Käufe an diesem Tag gehören nicht dazu.
 */
export function tradeMarks(series: HistoryPoint[], trades: Trade[]): TradeMark[] {
  if (series.length < 2) return [];
  const first = series[0].date, last = series[series.length - 1].date;
  const byIndex = new Map<number, Trade[]>();
  for (const trade of trades) {
    const day = trade.date.slice(0, 10);
    if (day <= first || day > last) continue;
    const index = series.findIndex((point) => point.date >= day);
    byIndex.set(index, [...(byIndex.get(index) ?? []), trade]);
  }
  return [...byIndex].sort(([a], [b]) => a - b).map(([index, list]) => ({ index, trades: list }));
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

export type SortKey = 'name' | 'quantity' | 'price' | 'day' | 'value' | 'gain';
export type Sort = { key: SortKey; dir: 1 | -1 };

export function sortRows(rows: PositionRow[], { key, dir }: Sort) {
  // Ohne Tageskurs zählt die Position wie unbewegt
  const number = (row: PositionRow) => (key === 'day' ? row.dayPct ?? 0 : row[key as Exclude<SortKey, 'name' | 'day'>]);
  return [...rows].sort((a, b) => (key === 'name' ? a.name.localeCompare(b.name, 'de') : number(a) - number(b)) * dir);
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
/** Rundungsreste bei Bruchstücken gelten als gleich, wie QUANTITY_EPSILON auf dem Server */
export const QUANTITY_EPSILON = 1e-6;

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
