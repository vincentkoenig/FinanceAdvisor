// Zahlen und Daten im deutschen Format, wie im Prototyp: echtes Minuszeichen,
// Plus nur wo ausdrücklich gewünscht, Datumswerte der API als JJJJ-MM-TT.

const MINUS = '−';
const formats = new Map<string, Intl.NumberFormat>();

function nf(min: number, max: number) {
  const key = `${min}-${max}`;
  let format = formats.get(key);
  if (!format) {
    format = new Intl.NumberFormat('de-DE', { minimumFractionDigits: min, maximumFractionDigits: max });
    formats.set(key, format);
  }
  return format;
}

function signOf(value: number, withPlus: boolean) {
  if (value < 0) return MINUS;
  return withPlus && value > 0 ? '+' : '';
}

/** 1234.5 → "1.234,50 €"; mit sign: "+1.234,50 €"; mit digits: 0 → "1.235 €" */
export function eur(value: number, { sign = false, digits = 2 }: { sign?: boolean; digits?: number } = {}) {
  // −0,00 € vermeiden: was auf null rundet, bekommt kein Vorzeichen
  const rounded = Number(value.toFixed(digits));
  return signOf(rounded, sign) + nf(digits, digits).format(Math.abs(rounded)) + ' €';
}

/** 2.345 → "+2,3 %" */
export function pct(value: number, { sign = true }: { sign?: boolean } = {}) {
  const rounded = Number(value.toFixed(1));
  return signOf(rounded, sign) + nf(1, 1).format(Math.abs(rounded)) + ' %';
}

/** Stückzahl mit bis zu sechs Nachkommastellen: 0.081 → "0,081" */
export function qty(value: number) {
  return nf(0, 6).format(value);
}

/** Klasse für Gewinn/Verlust */
export function tone(value: number) {
  return value > 0 ? 'pos' : value < 0 ? 'neg' : 'muted';
}

/** Klasse für einen Prozentwert, nach dem angezeigten Wert: −0,04 % wird zu "0,0 %" und bleibt grau */
export function pctTone(value: number) {
  return tone(Number(value.toFixed(1)));
}

/** "2026-10-03" → Datum um 12 Uhr Ortszeit (keine Verschiebung durch Zeitzonen) */
export function parseDay(iso: string) {
  return new Date(iso.slice(0, 10) + 'T12:00:00');
}

/** "2026-10-03" → "3. Okt." */
export function dayShort(iso: string | Date) {
  const day = typeof iso === 'string' ? parseDay(iso) : iso;
  return day.toLocaleDateString('de-DE', { day: 'numeric', month: 'short' });
}

/** Datum → "Oktober" */
export function monthName(day: Date) {
  return day.toLocaleDateString('de-DE', { month: 'long' });
}

/** Datum → "2026-10" */
export function monthKey(day: Date) {
  return `${day.getFullYear()}-${String(day.getMonth() + 1).padStart(2, '0')}`;
}

/** Datum → "2026-10-03" (Ortszeit) */
export function isoDay(day: Date) {
  return `${monthKey(day)}-${String(day.getDate()).padStart(2, '0')}`;
}

/** "1.234,5" oder "1234.5" → 1234.5; leer → null; sonst NaN */
export function parseAmount(text: string): number | null {
  const cleaned = text.replace(/[€\s]/g, '');
  if (cleaned === '') return null;
  const normalized = cleaned.includes(',') ? cleaned.replace(/\./g, '').replace(',', '.') : cleaned;
  return /^-?\d+(\.\d+)?$/.test(normalized) ? Number(normalized) : NaN;
}
