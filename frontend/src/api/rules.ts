// Regeln für den Kontoimport: Wort im Empfänger/Verwendungszweck -> Kategorie.
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from './client';

export type Rule = { id: number; pattern: string; income: boolean; category_id: number; category_label: string | null };
export type NewRule = { pattern: string; income: boolean; category_id: number };

const rulesKey = ['category-rules'] as const;

export const useRules = () => useQuery({ queryKey: rulesKey, queryFn: () => api<Rule[]>('/me/category-rules') });

export function useAddRule() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: NewRule) => api<{ message: string }>('/me/category-rules', { method: 'POST', body }),
    onSuccess: () => client.invalidateQueries({ queryKey: rulesKey }),
  });
}

export function useDeleteRule() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api<{ message: string }>(`/me/category-rules/${id}`, { method: 'DELETE' }),
    onSuccess: () => client.invalidateQueries({ queryKey: rulesKey }),
  });
}
