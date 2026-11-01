// Verträge: Übersicht mit Fristen und Summen, anlegen, bearbeiten, kündigen, Kündigung zurücknehmen, löschen.
// Fristen rechnet der Server (contracts/terms.py); jede Änderung lädt die Übersicht neu, Änderungen an der
// Buchung im Haushaltsbuch (verknüpfen, kündigen) auch die Buchungslisten und die Monatszusammenfassung.
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from './client';
import { keys } from './overview';

export type ContractCategory = 'insurance' | 'energy' | 'telecom' | 'subscription' | 'fitness' | 'loan' | 'other';
export type PaymentInterval = 'monthly' | 'quarterly' | 'half_yearly' | 'yearly';
export type NoticeUnit = 'days' | 'weeks' | 'months';
export type ContractStatus = 'active' | 'cancelled' | 'ending' | 'ended';

/** Was beim Anlegen und Bearbeiten geschickt wird */
export type ContractInput = {
  name: string;
  provider: string | null;
  category: ContractCategory;
  contract_number: string | null;
  amount: number;
  interval: PaymentInterval;
  start_date: string;
  min_term_months: number | null;
  renewal_months: number | null;
  notice_value: number;
  notice_unit: NoticeUnit;
  notes: string | null;
};

export type Contract = ContractInput & {
  id: number;
  cancelled_at: string | null;
  end_date: string | null;
  status: ContractStatus;
  next_term_end: string | null;
  /** Letzter Tag für die Kündigung … */
  cancel_by: string | null;
  /** … und zu welchem Tag der Vertrag dann endet */
  cancel_effective: string | null;
  days_to_cancel: number | null;
  ends_on: string | null;
  /** Ende der Mindestlaufzeit, falls es eine gibt */
  min_term_end: string | null;
  /** Verknüpfte wiederkehrende Buchung im Haushaltsbuch (Beitrag anteilig pro Monat) */
  booking: { id: number; amount: number; category_name: string | null; end_date: string | null } | null;
  yearly_cost: number;
  monthly_cost: number;
};

export type ContractsOverview = { contracts: Contract[]; yearly_total: number; monthly_total: number };

export const contractKeys = { all: ['contracts'] as const };

export const useContracts = () =>
  useQuery({ queryKey: contractKeys.all, queryFn: () => api<ContractsOverview>('/me/contracts'), staleTime: 60_000 });

type Saved = { message: string; contract: Contract };

function useChange<T, R>(request: (input: T) => Promise<R>) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: request,
    // Verknüpfte Buchungen ändern sich mit (Ende bei Kündigung), darum auch das Haushaltsbuch neu laden
    onSuccess: () => Promise.all([contractKeys.all, keys.bookings, keys.budgetSummary]
      .map((queryKey) => client.invalidateQueries({ queryKey }))),
  });
}

export const useAddContract = () =>
  useChange((body: ContractInput) => api<Saved>('/me/contracts', { method: 'POST', body }));

export const useUpdateContract = () =>
  useChange(({ id, body }: { id: number; body: ContractInput }) => api<Saved>(`/me/contracts/${id}`, { method: 'PUT', body }));

/** Ohne end_date endet der Vertrag zum nächstmöglichen Termin */
export const useCancelContract = () =>
  useChange(({ id, end_date }: { id: number; end_date: string | null }) =>
    api<Saved>(`/me/contracts/${id}/cancel`, { method: 'POST', body: { end_date } }));

export const useUndoCancel = () =>
  useChange((id: number) => api<Saved>(`/me/contracts/${id}/cancel`, { method: 'DELETE' }));

export const useDeleteContract = () =>
  useChange((id: number) => api(`/me/contracts/${id}`, { method: 'DELETE' }));

/** Neue Fixkosten-Buchung in category_id anlegen oder vorhandene wiederkehrende Buchung transaction_id übernehmen */
export const useLinkBooking = () =>
  useChange(({ id, ...body }: { id: number; category_id?: number; transaction_id?: number }) =>
    api<Saved>(`/me/contracts/${id}/booking`, { method: 'POST', body }));

/** Verknüpfung lösen, die Buchung bleibt im Haushaltsbuch */
export const useUnlinkBooking = () =>
  useChange((id: number) => api<Saved>(`/me/contracts/${id}/booking`, { method: 'DELETE' }));
