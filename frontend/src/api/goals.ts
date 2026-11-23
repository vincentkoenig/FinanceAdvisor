// Sparziele als Töpfe vom Kontostand: anlegen, ändern, einzahlen, entnehmen, löschen.
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from './client';

export type GoalPlan = {
  /** on_track: Rate reicht bis zum Datum; behind: zu wenig; overdue: Datum vorbei, Ziel nicht erreicht */
  status: 'on_track' | 'behind' | 'overdue';
  needed_monthly: number;
  months_left: number;
  shortfall_monthly?: number;
};

export type Goal = {
  id: number;
  name: string;
  target_amount: number;
  target_date: string | null;
  monthly_amount: number | null;
  balance: number;
  missing: number;
  /** 0 bis 1 */
  progress: number;
  reached: boolean;
  /** Nur mit Zieldatum und solange noch etwas fehlt */
  plan: GoalPlan | null;
};

export type GoalsOverview = {
  goals: Goal[];
  total: number;
  cash_balance: number | null;
  /** So viel mehr liegt in den Töpfen als auf dem Konto (0 = alles gedeckt) */
  over_by: number;
};

export type GoalInput = {
  name: string;
  target_amount: number;
  target_date: string | null;
  monthly_amount: number | null;
  start_amount?: number | null;
};

const goalsKey = ['goals'] as const;

export const useGoals = () =>
  useQuery({ queryKey: goalsKey, queryFn: () => api<GoalsOverview>('/me/goals'), staleTime: 60_000 });

function useGoalChange<T>(request: (input: T) => Promise<{ message: string }>) {
  const client = useQueryClient();
  return useMutation({ mutationFn: request, onSuccess: () => client.invalidateQueries({ queryKey: goalsKey }) });
}

export const useAddGoal = () =>
  useGoalChange((body: GoalInput) => api<{ message: string }>('/me/goals', { method: 'POST', body }));

export const useUpdateGoal = () =>
  useGoalChange(({ id, ...body }: GoalInput & { id: number }) => api<{ message: string }>(`/me/goals/${id}`, { method: 'PUT', body }));

export const useDeleteGoal = () =>
  useGoalChange((id: number) => api<{ message: string }>(`/me/goals/${id}`, { method: 'DELETE' }));

/** amount positiv = einzahlen, negativ = entnehmen */
export const useGoalEntry = () =>
  useGoalChange(({ id, amount, note }: { id: number; amount: number; note: string | null }) =>
    api<{ message: string }>(`/me/goals/${id}/entries`, { method: 'POST', body: { amount, note } }));
