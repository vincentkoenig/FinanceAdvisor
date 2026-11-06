// Eingetragene Kontostände und der Vermögensverlauf. Eine Änderung verschiebt den Cash-Bestand,
// darum laden Übersicht und Verlauf danach neu.
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from './client';
import { keys } from './overview';

export type Balance = { id: number; date: string; amount: number; expected: number | null; difference: number | null };
export type WealthPoint = { date: string; cash: number; depot: number; total: number };

const minute = 60_000;

export const useBalances = () =>
  useQuery({ queryKey: keys.balances, queryFn: () => api<Balance[]>('/me/balances'), staleTime: minute });

export const useWealthHistory = () =>
  useQuery({ queryKey: keys.wealth, queryFn: () => api<WealthPoint[]>('/me/wealth/history'), staleTime: 10 * minute });

function useRefresh() {
  const client = useQueryClient();
  return () => Promise.all([keys.balances, keys.wealth, keys.budgetSummary].map((queryKey) => client.invalidateQueries({ queryKey })));
}

export function useSaveBalance() {
  const refresh = useRefresh();
  return useMutation({
    mutationFn: (body: { date: string; amount: number }) => api('/me/balances', { method: 'POST', body }),
    onSuccess: refresh,
  });
}

export function useDeleteBalance() {
  const refresh = useRefresh();
  return useMutation({
    mutationFn: (id: number) => api(`/me/balances/${id}`, { method: 'DELETE' }),
    onSuccess: refresh,
  });
}
