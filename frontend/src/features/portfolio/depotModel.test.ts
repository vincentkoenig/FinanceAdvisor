import { strToU8, zipSync } from 'fflate';
import { describe, expect, it } from 'vitest';
import type { DepotRow } from '../../api/imports';
import { recheckSales } from './depotModel';
import { filesFromZip, isZip } from './zip';

const row = (over: Partial<DepotRow> & Pick<DepotRow, 'key' | 'type' | 'date' | 'quantity'>): DepotRow => ({
  isin: 'IE00B4L5Y983', name: 'Welt', price: 100, quote: 100, fees: 0, symbol: 'EUNL.DE', asset_name: 'Welt', asset_id: 1, status: 'new', ...over,
});
const all = (rows: DepotRow[]) => Object.fromEntries(rows.map((r) => [r.key, true]));

describe('recheckSales', () => {
  it('nimmt für einen Verkauf die Stücke aus einem Kauf in einer anderen Datei', () => {
    const rows = [
      row({ key: 'v', type: 'sell', date: '2025-06-01', quantity: 5, status: 'insufficient' }),
      row({ key: 'k', type: 'buy', date: '2025-01-01', quantity: 10 }),
    ];
    expect(recheckSales(rows, {}, all(rows)).get('v')).toBe('new');
  });

  it('rechnet Kauf, Verkauf, Kauf in zeitlicher Reihenfolge', () => {
    const rows = [
      row({ key: 'k2', type: 'buy', date: '2025-03-01', quantity: 10 }),
      row({ key: 'v', type: 'sell', date: '2025-02-01', quantity: 10, status: 'insufficient' }),
      row({ key: 'k1', type: 'buy', date: '2025-01-01', quantity: 10 }),
      row({ key: 'v2', type: 'sell', date: '2025-04-01', quantity: 10, status: 'insufficient' }),
    ];
    const status = recheckSales(rows, {}, all(rows));
    expect([status.get('v'), status.get('v2')]).toEqual(['new', 'new']);
  });

  it('bucht am selben Tag erst den Kauf', () => {
    const rows = [
      row({ key: 'v', type: 'sell', date: '2025-01-01', quantity: 1, status: 'insufficient' }),
      row({ key: 'k', type: 'buy', date: '2025-01-01', quantity: 1 }),
    ];
    expect(recheckSales(rows, {}, all(rows)).get('v')).toBe('new');
  });

  it('meldet einen Verkauf ohne passende Stücke weiter und zählt vorhandene Stücke mit', () => {
    const rows = [row({ key: 'v', type: 'sell', date: '2025-01-01', quantity: 5, status: 'insufficient' })];
    expect(recheckSales(rows, {}, all(rows)).get('v')).toBe('insufficient');
    expect(recheckSales(rows, { 'eunl.de': 5 }, all(rows)).get('v')).toBe('new');
  });

  it('zählt abgewählte Käufe nicht, weil sie nicht gebucht werden', () => {
    const rows = [
      row({ key: 'k', type: 'buy', date: '2025-01-01', quantity: 10 }),
      row({ key: 'v', type: 'sell', date: '2025-02-01', quantity: 5, status: 'insufficient' }),
    ];
    expect(recheckSales(rows, {}, { k: false, v: true }).get('v')).toBe('insufficient');
  });

  it('lässt schon gebuchte und ungültige Zeilen, wie sie sind', () => {
    const rows = [row({ key: 'd', type: 'buy', date: '2025-01-01', quantity: 1, status: 'duplicate' }), row({ key: 'u', type: 'sell', date: '2025-01-02', quantity: 1, status: 'unknown', symbol: null })];
    const status = recheckSales(rows, {}, all(rows));
    expect([status.get('d'), status.get('u')]).toEqual(['duplicate', 'unknown']);
  });

  it('kennt Wertpapiere nach Symbol getrennt', () => {
    const rows = [
      row({ key: 'k', type: 'buy', date: '2025-01-01', quantity: 10, symbol: 'SAP.DE' }),
      row({ key: 'v', type: 'sell', date: '2025-02-01', quantity: 5, status: 'insufficient' }),
    ];
    expect(recheckSales(rows, {}, all(rows)).get('v')).toBe('insufficient');
  });
});

describe('filesFromZip', () => {
  const archive = (entries: Record<string, string>) => {
    const packed = zipSync(Object.fromEntries(Object.entries(entries).map(([name, text]) => [name, new Uint8Array(strToU8(text))])));
    return new File([packed.slice()], 'abrechnungen.zip', { type: 'application/zip' });
  };

  it('holt PDFs und CSVs auch aus Ordnern, ohne Systemdateien', async () => {
    const files = await filesFromZip(archive({
      'Depot/b Verkauf.PDF': 'b', 'a Kauf.pdf': 'a', 'liste.csv': 'c', 'bild.png': 'x', '__MACOSX/a Kauf.pdf': 'x', '.hidden.pdf': 'x',
    }));
    expect(files.map((f) => f.name)).toEqual(['a Kauf.pdf', 'b Verkauf.PDF', 'liste.csv']);
    expect(files[0].type).toBe('application/pdf');
  });

  it('sagt, wenn nichts Passendes drin ist oder die Datei kaputt ist', async () => {
    await expect(filesFromZip(archive({ 'bild.png': 'x' }))).rejects.toThrow('keine PDF- oder CSV-Dateien');
    await expect(filesFromZip(new File(['kein zip'], 'x.zip'))).rejects.toThrow('ließ sich nicht öffnen');
  });

  it('erkennt ZIP-Dateien', () => {
    expect(isZip(new File([], 'Abrechnungen.ZIP'))).toBe(true);
    expect(isZip(new File([], 'a.pdf'))).toBe(false);
  });
});
