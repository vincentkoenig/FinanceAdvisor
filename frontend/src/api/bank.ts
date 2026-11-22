// Bankabruf über Enable Banking: Zugänge, Konten, jetzt abrufen und die Prüfliste wartender Umsätze.
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from './client';
import type { ImportPreview } from './imports';
import { keys } from './overview';

export type BankAccount = { id: number; name: string | null; iban_last4: string | null; enabled: boolean; synced_until: string | null };

export type BankConnection = {
  id: number;
  aspsp_name: string;
  status: 'active' | 'expired' | 'error';
  /** Bis wann die Bank die Freigabe erteilt hat (UTC) */
  valid_until: string | null;
  last_sync_at: string | null;
  last_error: string | null;
  accounts: BankAccount[];
};

export type BankOverview = {
  /** Server hat App-ID und Schlüssel von Enable Banking */
  configured: boolean;
  /** Muss genau so in der Enable-Banking-App eingetragen sein */
  redirect_url: string;
  review_count: number;
  connections: BankConnection[];
};

export type SyncResult = { booked: number; review: number; covered: number; duplicate: number; balance: number | null; errors: string[] };

export const bankKeys = {
  overview: ['bank'] as const,
  aspsps: ['bank', 'aspsps'] as const,
  review: ['bank', 'review'] as const,
};

const minute = 60_000;

export const useBank = () =>
  useQuery({ queryKey: bankKeys.overview, queryFn: () => api<BankOverview>('/me/bank'), staleTime: minute });

export const useAspsps = (enabled: boolean) =>
  useQuery({
    queryKey: bankKeys.aspsps,
    queryFn: () => api<{ configured: boolean; aspsps: string[] }>('/me/bank/aspsps').then((r) => r.aspsps),
    enabled,
    staleTime: 60 * minute,
  });

/** Anmeldung bei der Bank starten; danach geht es auf der Seite der Bank weiter */
export const useConnectBank = () =>
  useMutation({
    mutationFn: (aspspName: string) => api<{ url: string }>('/me/bank/connect', { method: 'POST', body: { aspsp_name: aspspName } }),
    onSuccess: ({ url }) => window.location.assign(url),
  });

function useAfterBank() {
  const client = useQueryClient();
  return () => Promise.all([bankKeys.overview, keys.bookings, keys.budgetSummary, keys.balances, keys.wealth]
    .map((queryKey) => client.invalidateQueries({ queryKey })));
}

export function useSyncBank() {
  const after = useAfterBank();
  return useMutation({ mutationFn: () => api<SyncResult>('/me/bank/sync', { method: 'POST' }), onSettled: after });
}

export function useToggleBankAccount() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ id, enabled }: { id: number; enabled: boolean }) => api(`/me/bank/accounts/${id}`, { method: 'PUT', body: { enabled } }),
    onSuccess: () => client.invalidateQueries({ queryKey: bankKeys.overview }),
  });
}

export function useDisconnectBank() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api(`/me/bank/connections/${id}`, { method: 'DELETE' }),
    onSuccess: () => client.invalidateQueries({ queryKey: bankKeys.overview }),
  });
}

/** Wartende Umsätze in der Form der Import-Vorschau (key "bank-<id>") */
export const useBankReview = (enabled: boolean) =>
  useQuery({ queryKey: bankKeys.review, queryFn: () => api<ImportPreview>('/me/bank/review'), enabled, staleTime: 0 });

export type ReviewCommit = { book: { id: number; category_id: number; description: string }[]; dismiss: number[] };

export function useCommitBankReview() {
  const after = useAfterBank();
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: ReviewCommit) =>
      api<{ message: string; created: number; dismissed: number }>('/me/bank/review/commit', { method: 'POST', body }),
    onSuccess: () => Promise.all([after(), client.invalidateQueries({ queryKey: bankKeys.review })]),
  });
}
