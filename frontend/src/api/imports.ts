// Kontoumsätze aus dem CSV-Export der Bank und Depot-Abrechnungen (PDF): Vorschau (speichert nichts) und Übernehmen.
// Die Vorschau schickt die Datei selbst statt JSON, darum hier ein eigener fetch statt api().
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { API_PREFIX, ApiError, api } from './client';
import { keys } from './overview';

export type ImportField = 'date' | 'amount' | 'debit' | 'credit' | 'sign' | 'counterparty' | 'purpose' | 'currency';
export type ColumnMapping = Partial<Record<ImportField, number>>;

export type ImportStatus = 'new' | 'covered' | 'duplicate';

export type ImportRow = {
  key: string;
  occurrence: number;
  line: number;
  date: string;
  /** Ausgaben negativ, Einnahmen positiv */
  amount: number;
  counterparty: string;
  purpose: string;
  description: string;
  status: ImportStatus;
  covered_by: { id: number; description: string | null; amount: number } | null;
  category_id: number | null;
};

export type ImportPreview = {
  columns: string[];
  mapping: ColumnMapping;
  rows: ImportRow[];
  skipped: { line: number; reason: string }[];
  counts: Record<ImportStatus, number>;
};

/** Die Spalten wurden nicht erkannt: columns nennt sie, damit man sie zuordnen kann */
export class UnknownColumnsError extends ApiError {
  columns: string[];

  constructor(message: string, columns: string[]) {
    super(400, message);
    this.columns = columns;
  }
}

export async function previewBankImport(file: File, mapping?: ColumnMapping): Promise<ImportPreview> {
  // Die Datei geht unverändert als Inhalt der Anfrage (Bytes, damit Windows-1252 erhalten bleibt),
  // die Spaltenzuordnung als URL-Parameter - sie enthält nur Spaltennummern
  const query = mapping ? `?mapping=${encodeURIComponent(JSON.stringify({ columns: mapping }))}` : '';
  let response: Response;
  try {
    response = await fetch(`${API_PREFIX}/me/import/bank/preview${query}`, {
      method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'text/csv' }, body: await file.arrayBuffer(),
    });
  } catch {
    throw new ApiError(0, 'Keine Verbindung zum Server. Bitte prüfe deine Internetverbindung.');
  }
  const data = await response.json().catch(() => null);
  if (!response.ok) {
    const message = data?.error ?? `Unerwartete Antwort vom Server (${response.status})`;
    if (Array.isArray(data?.columns)) throw new UnknownColumnsError(message, data.columns);
    throw new ApiError(response.status, message, data?.fields ?? {});
  }
  return data as ImportPreview;
}

export const usePreviewBankImport = () =>
  useMutation({ mutationFn: ({ file, mapping }: { file: File; mapping?: ColumnMapping }) => previewBankImport(file, mapping) });

export type CommitRow = Pick<ImportRow, 'date' | 'amount' | 'counterparty' | 'purpose' | 'occurrence' | 'description'> & { category_id: number };

export function useCommitBankImport() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (rows: CommitRow[]) =>
      api<{ message: string; created: number; skipped: number }>('/me/import/bank/commit', { method: 'POST', body: { rows } }),
    onSuccess: () => Promise.all([keys.bookings, keys.budgetSummary].map((queryKey) => client.invalidateQueries({ queryKey }))),
  });
}

// ─── DEPOT-ABRECHNUNGEN (PDF) ────────────────────────────────────────────────

export type DepotStatus = 'new' | 'duplicate' | 'unknown' | 'insufficient';

export type DepotRow = {
  key: string;
  type: 'buy' | 'sell';
  isin: string;
  name: string;
  date: string;
  quantity: number;
  /** Kurs inklusive Gebühren je Stück (so wird gebucht) */
  price: number | null;
  /** Kurs laut Abrechnung, ohne Gebühren */
  quote: number;
  fees: number;
  symbol: string | null;
  asset_name: string | null;
  asset_id: number | null;
  status: DepotStatus;
};

export type DepotPreview = { is_trade_statement: boolean; note: string | null; rows: DepotRow[]; sent_text: string };

export async function previewDepotImport(file: File): Promise<DepotPreview> {
  let response: Response;
  try {
    response = await fetch(`${API_PREFIX}/me/import/depot/preview`, {
      method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/pdf' }, body: await file.arrayBuffer(),
    });
  } catch {
    throw new ApiError(0, 'Keine Verbindung zum Server. Bitte prüfe deine Internetverbindung.');
  }
  const data = await response.json().catch(() => null);
  if (!response.ok) throw new ApiError(response.status, data?.error ?? `Unerwartete Antwort vom Server (${response.status})`);
  return data as DepotPreview;
}

export type CryptoField = 'date' | 'type' | 'asset' | 'quantity' | 'price' | 'total' | 'fee';
export type CryptoMapping = Partial<Record<CryptoField, number>>;
export type CryptoPreview = { rows: DepotRow[]; skipped: { line: number; reason: string }[]; columns: string[] };

/** CSV-Export einer Krypto-App (z. B. Bison), ohne KI; gebucht wird wie bei Abrechnungen */
export async function previewCryptoImport(file: File, mapping?: CryptoMapping): Promise<CryptoPreview> {
  const query = mapping ? `?mapping=${encodeURIComponent(JSON.stringify({ columns: mapping }))}` : '';
  let response: Response;
  try {
    response = await fetch(`${API_PREFIX}/me/import/crypto/preview${query}`, {
      method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'text/csv' }, body: await file.arrayBuffer(),
    });
  } catch {
    throw new ApiError(0, 'Keine Verbindung zum Server. Bitte prüfe deine Internetverbindung.');
  }
  const data = await response.json().catch(() => null);
  if (!response.ok) {
    const message = data?.error ?? `Unerwartete Antwort vom Server (${response.status})`;
    if (Array.isArray(data?.columns)) throw new UnknownColumnsError(message, data.columns);
    throw new ApiError(response.status, message, data?.fields ?? {});
  }
  return data as CryptoPreview;
}

export type DepotCommitTrade = { type: 'buy' | 'sell'; symbol: string; name: string; date: string; quantity: number; price: number };

export function useCommitDepotImport() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (trades: DepotCommitTrade[]) =>
      api<{ message: string; booked: number; skipped: number }>('/me/import/depot/commit', { method: 'POST', body: { trades } }),
    onSuccess: () => Promise.all([keys.positions, keys.trades, keys.history].map((queryKey) => client.invalidateQueries({ queryKey }))),
  });
}
