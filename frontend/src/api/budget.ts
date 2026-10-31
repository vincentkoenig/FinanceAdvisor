// Haushaltsbuch: Kategorien, Buchungen eines Monats, neue Buchung, Pausieren und Löschen.
// Jede Änderung lädt alle Buchungslisten und die Monatszusammenfassung (auch die der Übersicht) neu.
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from './client';
import { type Booking, type CategoryType, keys } from './overview';

export type Category = { id: number; name: string; type: CategoryType; parent_id: number | null };

export const budgetKeys = {
  categories: ['categories'] as const,
  // Beginnt wie keys.bookings, damit das Neuladen aller Buchungen auch die Monatslisten trifft
  month: (month: string) => [...keys.bookings, month] as const,
};

const minute = 60_000;

export const useCategories = () =>
  useQuery({ queryKey: budgetKeys.categories, queryFn: () => api<Category[]>('/me/categories'), staleTime: 10 * minute });

/** Buchungen eines Monats ("2026-10"); wiederkehrende stehen in jedem Monat, in dem sie laufen */
export const useMonthBookings = (month: string) =>
  useQuery({ queryKey: budgetKeys.month(month), queryFn: () => api<Booking[]>(`/me/transactions?month=${month}`), staleTime: minute });

function useRefresh() {
  const client = useQueryClient();
  return () => Promise.all([keys.bookings, keys.budgetSummary].map((queryKey) => client.invalidateQueries({ queryKey })));
}

export type NewBooking = {
  category_id: number;
  amount: number;
  description: string | null;
  date: string;
  is_recurring: boolean;
  end_date: string | null;
};

export function useAddBooking() {
  const refresh = useRefresh();
  return useMutation({
    mutationFn: (body: NewBooking) => api('/me/transactions', { method: 'POST', body }),
    onSuccess: refresh,
  });
}

export function useTogglePause() {
  const refresh = useRefresh();
  return useMutation({
    mutationFn: (id: number) => api<{ is_paused: boolean }>(`/me/transactions/${id}/toggle-pause`, { method: 'POST' }),
    onSuccess: refresh,
  });
}

export function useDeleteBooking() {
  const refresh = useRefresh();
  return useMutation({
    mutationFn: (id: number) => api(`/me/transactions/${id}`, { method: 'DELETE' }),
    onSuccess: refresh,
  });
}

/** Für neue Konten: die Standardkategorien anlegen */
export function useDefaultCategories() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: () => api('/me/categories/init-defaults', { method: 'POST' }),
    onSuccess: () => client.invalidateQueries({ queryKey: budgetKeys.categories }),
  });
}
