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
  /** Zielkurs in Euro; die Richtung ergibt sich beim Setzen aus dem aktuellen Kurs */
  target_price: number | null;
  target_direction: 'above' | 'below' | null;
  /** Tag, an dem der Zielkurs erreicht und gemeldet wurde */
  target_hit: string | null;
};

export type Asset = { id: number; name: string; symbol: string; asset_type: string | null; current_price: number | null };

export type Lot = {
  bought_on: string;
  quantity: number;
  /** Einstand je Stück inklusive Kaufgebühren */
  unit_cost: number;
  cost: number;
  value: number | null;
  gain: number | null;
  gain_pct: number | null;
  /** Stücke ohne einzelne Kaufbuchung, zum Durchschnittspreis der Position */
  opening: boolean;
  /** Nur Krypto: erster Tag, an dem ein Verkauf dieses Postens steuerfrei wäre */
  tax_free_from: string | null;
};

export type Sale = {
  asset_id: number;
  name: string;
  symbol: string;
  asset_type: string | null;
  bucket: 'stock' | 'other' | 'crypto';
  date: string;
  first_bought: string | null;
  quantity: number;
  proceeds: number;
  cost: number;
  gain: number;
  /** Krypto nach mehr als einem Jahr Haltedauer */
  tax_free: boolean;
  /** Mehr verkauft als gebucht: Einstand unbekannt, Gewinn als 0 gezählt */
  unknown_cost: boolean;
};

export type RealizedGains = {
  year: number;
  years: number[];
  sales: Sale[];
  securities: {
    stock_gains: number; other_gains: number; dividends: number; taxable: number;
    allowance: number; joint: boolean; allowance_used: number; allowance_left: number; above_allowance: number; stock_loss_carried: number;
  };
  crypto: { taxable_gains: number; tax_free_gains: number; exemption_limit: number; over_limit: boolean };
};

export const portfolioKeys = {
  watchlist: ['watchlist'] as const,
  lots: (assetId: number) => ['lots', assetId] as const,
  realized: (year: number) => ['realized-gains', year] as const,
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

/** Offene Kaufposten einer Position nach FIFO (älteste zuerst) */
export const useLots = (assetId: number) =>
  useQuery({
    queryKey: portfolioKeys.lots(assetId),
    queryFn: () => api<{ current_price: number | null; lots: Lot[] }>(`/me/positions/${assetId}/lots`),
    staleTime: 2 * minute,
  });

/** Realisierte Gewinne eines Jahres mit geschätztem Sparerpauschbetrag */
export const useRealizedGains = (year: number) =>
  useQuery({
    queryKey: portfolioKeys.realized(year),
    queryFn: () => api<RealizedGains>(`/me/realized-gains?year=${year}`),
    staleTime: 10 * minute,
  });

/** Gemeinsam veranlagt (verheiratet): Sparerpauschbetrag 2.000 € statt 1.000 € */
export function useTaxJoint() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (taxJoint: boolean) => api<{ tax_joint: boolean }>('/me/tax-settings', { method: 'PUT', body: { tax_joint: taxJoint } }),
    onSuccess: () => invalidate(['realized-gains']),
  });
}

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

const afterTrade = [keys.positions, keys.history, keys.performance, keys.trades, ['lots'], ['realized-gains']];

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

export function useSetTarget() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: ({ asset_id, target_price }: { asset_id: number; target_price: number | null }) =>
      api<{ target_price: number | null; target_direction: 'above' | 'below' | null }>(`/me/watchlist/${asset_id}/target`, { method: 'PUT', body: { target_price } }),
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
