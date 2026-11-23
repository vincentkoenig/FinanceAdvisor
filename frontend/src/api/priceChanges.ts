// Preisänderungen, die FinTrack an den Abbuchungen erkannt hat (Verträge und wiederkehrende Buchungen).
// Eigene Datei, damit sie nicht mit den Verträgen in den Start der App wandert.
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from './client';
import { type Contract, contractKeys } from './contracts';
import { keys } from './overview';

export type PriceChange = {
  /** z.B. "price:contract:12:13.99" - zum Übernehmen oder Ignorieren */
  key: string;
  kind: 'contract' | 'booking';
  id: number;
  name: string;
  interval: Contract['interval'];
  old_amount: number;
  new_amount: number;
  /** Erste Abbuchung zum neuen Preis */
  since: string;
  charges: number;
  yearly_difference: number;
};

const priceKey = ['price-changes'] as const;

export const usePriceChanges = () =>
  useQuery({ queryKey: priceKey, queryFn: () => api<PriceChange[]>('/me/price-changes'), staleTime: 60_000 });

function usePriceAction(path: 'accept' | 'dismiss') {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (key: string) => api<{ message: string }>(`/me/price-changes/${path}`, { method: 'POST', body: { key } }),
    onSuccess: () => Promise.all([priceKey, contractKeys.all, keys.bookings, keys.budgetSummary, keys.balances, keys.wealth]
      .map((queryKey) => client.invalidateQueries({ queryKey }))),
  });
}

export const useAcceptPriceChange = () => usePriceAction('accept');
export const useDismissPriceChange = () => usePriceAction('dismiss');
