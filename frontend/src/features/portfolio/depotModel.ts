// Logik des Abrechnungs-Imports ohne Oberfläche. Der Server prüft jede Datei für sich und sieht nur
// schon gebuchte Stücke. Ob ein Verkauf aufgeht, entscheidet sich hier über alle gewählten Dateien.
import type { DepotRow } from '../../api/imports';
import { QUANTITY_EPSILON } from './model';

const key = (row: Pick<DepotRow, 'symbol' | 'isin'>) => (row.symbol ?? row.isin).toUpperCase();

/**
 * Status je Ausführung nach Datum durchgerechnet, Käufe vor Verkäufen am selben Tag: Ein Verkauf ist
 * 'new', wenn die Stücke im Depot liegen oder von ausgewählten früheren Käufen kommen. Stücke
 * zählen nur aus ausgewählten Zeilen, denn nur die werden auch gebucht.
 */
export function recheckSales(rows: DepotRow[], held: Record<string, number>, selected: Record<string, boolean>) {
  const left = new Map(Object.entries(held).map(([symbol, quantity]) => [symbol.toUpperCase(), quantity]));
  const status = new Map<string, DepotRow['status']>();
  const inOrder = [...rows].sort((a, b) => a.date.localeCompare(b.date) || Number(a.type === 'sell') - Number(b.type === 'sell'));
  for (const row of inOrder) {
    const open = row.status === 'new' || row.status === 'insufficient';
    if (!open) {
      status.set(row.key, row.status);
      continue;
    }
    const pieces = left.get(key(row)) ?? 0;
    if (row.type === 'buy') {
      status.set(row.key, 'new');
      if (selected[row.key]) left.set(key(row), pieces + row.quantity);
    } else if (pieces + QUANTITY_EPSILON < row.quantity) {
      status.set(row.key, 'insufficient');
    } else {
      status.set(row.key, 'new');
      if (selected[row.key]) left.set(key(row), pieces - row.quantity);
    }
  }
  return status;
}
