// Bearbeiten im Portfolio: Assets suchen, kaufen, verkaufen, beobachten, Sparpläne anlegen und löschen.
// Nach jeder Änderung werden die Abfragen neu geladen, deren Zahlen sich dadurch ändern.
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useState } from 'react';
import { api } from './client';
import { keys } from './overview';

export type SearchResult = {
  asset_id: number | null;
  symbol: string;
  name: string;
  exchange: string | null;
  asset_type: string;
  eur: boolean;
};

export type WatchItem = {
  asset_id: number;
  name: string;
  symbol: string;
  price_added: number | null;
  current_price: number | null;
  added_at: string;
};

export type Asset = { id: number; name: string; symbol: string; asset_type: string | null; current_price: number | null };

export const portfolioKeys = {
  watchlist: ['watchlist'] as const,
  search: (query: string) => ['asset-search', query] as const,
  asset: (id: number) => ['asset', id] as const,
};

const minute = 60_000;

export const useWatchlist = () =>
  useQuery({ queryKey: portfolioKeys.watchlist, queryFn: () => api<WatchItem[]>('/me/watchlist'), staleTime: 2 * minute });

// Erst suchen, wenn 300 ms nicht mehr getippt wurde und mindestens zwei Zeichen da sind
export function useAssetSearch(query: string) {
  const [settled, setSettled] = useState(query.trim());
  useEffect(() => {
    const timer = setTimeout(() => setSettled(query.trim()), 300);
    return () => clearTimeout(timer);
  }, [query]);
  return useQuery({
    queryKey: portfolioKeys.search(settled),
    queryFn: () => api<{ results: SearchResult[] }>(`/assets/search?query=${encodeURIComponent(settled)}`).then((r) => r.results),
    enabled: settled.length >= 2,
    staleTime: 10 * minute,
  });
}

/** Kurs eines Assets, um den Kaufpreis vorzuschlagen */
export const useAsset = (id: number | null) =>
  useQuery({
    queryKey: portfolioKeys.asset(id ?? 0),
    queryFn: () => api<Asset>(`/assets/${id}`),
    enabled: id !== null,
    staleTime: 2 * minute,
  });

/** Gewählten Suchtreffer anlegen (oder das vorhandene Asset holen) und seine ID liefern */
export async function ensureAsset(result: SearchResult) {
  if (result.asset_id) return result.asset_id;
  const asset = await api<{ id: number }>('/assets', { method: 'POST', body: { symbol: result.symbol, name: result.name } });
  return asset.id;
}

function useInvalidate() {
  const client = useQueryClient();
  return (...queryKeys: readonly (readonly unknown[])[]) =>
    Promise.all(queryKeys.map((queryKey) => client.invalidateQueries({ queryKey })));
}

const afterTrade = [keys.positions, keys.history, keys.trades];

// Ein Kauf mit Datum; ist das Asset schon im Depot, ergibt das einen neuen Durchschnittspreis
export function useBuy() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (body: { asset_id: number; quantity: number; avg_buy_price: number; bought_at: string }) =>
      api('/me/positions', { method: 'POST', body }),
    onSuccess: () => invalidate(...afterTrade),
  });
}

// Verkauf zum angegebenen Preis, verbucht mit heutigem Datum (die API kennt kein Verkaufsdatum)
export function useSell() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: ({ asset_id, ...body }: { asset_id: number; quantity: number; price: number }) =>
      api(`/me/positions/${asset_id}/sell`, { method: 'POST', body }),
    onSuccess: () => invalidate(...afterTrade),
  });
}

export function useWatch() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (asset_id: number) => api('/me/watchlist', { method: 'POST', body: { asset_id } }),
    onSuccess: () => invalidate(portfolioKeys.watchlist),
  });
}

export function useUnwatch() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (asset_id: number) => api(`/me/watchlist/${asset_id}`, { method: 'DELETE' }),
    onSuccess: () => invalidate(portfolioKeys.watchlist),
  });
}

export function useCreatePlan() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (body: { asset_id: number; amount: number; day_of_month: number }) =>
      api('/me/savings-plans', { method: 'POST', body }),
    onSuccess: () => invalidate(keys.savingsPlans),
  });
}

export function useDeletePlan() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (id: number) => api(`/me/savings-plans/${id}`, { method: 'DELETE' }),
    onSuccess: () => invalidate(keys.savingsPlans),
  });
}
