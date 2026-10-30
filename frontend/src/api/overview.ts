// Daten für die Übersicht: alles kommt aus den bestehenden /me-Routen der API.
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from './client';

export type Position = {
  asset_id: number;
  name: string;
  symbol: string;
  asset_type: string | null;
  quantity: number;
  avg_buy_price: number;
  current_price: number | null;
};

export type BudgetSummary = {
  cumulative_balance: number;
  current_month_balance: number;
  current_month_income: number;
  current_month_fixed: number;
  current_month_variable: number;
};

export type HistoryPoint = { date: string; value: number };

export type SavingsPlan = {
  id: number;
  asset_id: number;
  asset_name: string;
  asset_symbol: string;
  amount: number;
  day_of_month: number;
  last_executed: string | null;
  is_due: boolean;
};

export type CategoryType = 'income' | 'fixed_expense' | 'variable_expense';

export type Booking = {
  id: number;
  amount: number;
  description: string | null;
  date: string;
  end_date?: string | null;
  is_recurring: boolean;
  is_paused: boolean;
  paused_at?: string | null;
  category_id?: number;
  category_name: string | null;
  category_type: CategoryType | null;
};

export type Trade = {
  id: number;
  asset_id: number;
  asset_name: string;
  asset_symbol: string;
  type: 'buy' | 'sell';
  quantity: number;
  price: number;
  total: number;
  date: string;
};

export type Dividend = {
  id: number;
  asset_name: string;
  asset_symbol: string;
  ex_dividend_date: string;
  amount_per_share: number;
  shares_held: number;
  total_amount: number;
};

export type Insight = { content: string | null; created_at?: string };

export const keys = {
  positions: ['positions'] as const,
  budgetSummary: ['budget', 'summary'] as const,
  history: ['portfolio', 'history'] as const,
  savingsPlans: ['savings-plans'] as const,
  bookings: ['transactions'] as const,
  insight: ['insight'] as const,
  trades: ['asset-transactions'] as const,
  dividends: ['dividends'] as const,
};

// Kurse ändern sich höchstens alle paar Minuten; beim Zurückkehren zur Seite reicht das
const minute = 60_000;

export const usePositions = () =>
  useQuery({ queryKey: keys.positions, queryFn: () => api<Position[]>('/me/positions'), staleTime: 2 * minute });

export const useBudgetSummary = () =>
  useQuery({ queryKey: keys.budgetSummary, queryFn: () => api<BudgetSummary>('/me/budget/summary'), staleTime: minute });

export const usePortfolioHistory = () =>
  useQuery({ queryKey: keys.history, queryFn: () => api<HistoryPoint[]>('/me/portfolio/history'), staleTime: 10 * minute });

export const useSavingsPlans = () =>
  useQuery({ queryKey: keys.savingsPlans, queryFn: () => api<SavingsPlan[]>('/me/savings-plans'), staleTime: minute });

export const useBookings = () =>
  useQuery({ queryKey: keys.bookings, queryFn: () => api<Booking[]>('/me/transactions'), staleTime: minute });

export const useTrades = () =>
  useQuery({ queryKey: keys.trades, queryFn: () => api<Trade[]>('/me/asset-transactions'), staleTime: minute });

export const useDividends = () =>
  useQuery({ queryKey: keys.dividends, queryFn: () => api<Dividend[]>('/me/dividends'), staleTime: 10 * minute });

export const useInsight = () =>
  useQuery({ queryKey: keys.insight, queryFn: () => api<Insight>('/me/insight'), staleTime: 30 * minute });

// Ein Sparplan kauft zum aktuellen Kurs: danach stimmen Positionen, Verlauf und Sparpläne nicht mehr
export function useExecutePlan() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (planId: number) =>
      api<{ quantity: number; price: number }>(`/me/savings-plans/${planId}/execute`, { method: 'POST' }),
    onSuccess: () => Promise.all([keys.positions, keys.history, keys.savingsPlans, keys.trades]
      .map((queryKey) => client.invalidateQueries({ queryKey }))),
  });
}
