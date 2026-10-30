// Anlageprofil speichern und eigene Daten importieren. Der Export ist ein normaler
// Download-Link auf /api/v1/me/export und braucht keinen Code.
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { meKey } from './auth';
import { api } from './client';

export type Profile = {
  risk_profile: string | null;
  investment_experience: string | null;
  monthly_budget: number | null;
  investment_horizon: string | null;
};

export function useSaveProfile() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (profile: Profile) => api<{ message: string }>('/me/settings', { method: 'PUT', body: profile }),
    onSuccess: () => client.invalidateQueries({ queryKey: meKey }),
  });
}

export type ImportCounts = Record<string, number>;

export function useImportData() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (payload: unknown) => api<{ imported: ImportCounts }>('/me/import', { method: 'POST', body: payload }),
    // Danach ist das Konto nicht mehr leer: alles neu laden, die Anmeldung bleibt
    onSuccess: () => client.invalidateQueries({ predicate: (query) => query.queryKey[0] !== meKey[0] }),
  });
}
