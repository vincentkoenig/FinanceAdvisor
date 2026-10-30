// Anmeldung über das Session-Cookie von Flask: /me sagt, wer angemeldet ist,
// Login und Logout setzen bzw. löschen das Cookie.
import { QueryCache, QueryClient, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ApiError, api } from './client';

export type User = {
  id: number;
  username: string | null;
  email: string;
  risk_profile: string | null;
  investment_experience: string | null;
  monthly_budget: number | null;
  investment_horizon: string | null;
};

export const meKey = ['me'] as const;

// Nicht angemeldet ist kein Fehler, sondern ein Zustand: /me gibt dann null zurück
async function fetchMe(): Promise<User | null> {
  try {
    return await api<User>('/me');
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) return null;
    throw error;
  }
}

export function useMe() {
  return useQuery({ queryKey: meKey, queryFn: fetchMe, staleTime: 5 * 60_000 });
}

export function useLogin() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (credentials: { email: string; password: string }) =>
      api<{ message: string }>('/auth/login', { method: 'POST', body: credentials }),
    onSuccess: () => client.invalidateQueries({ queryKey: meKey }),
  });
}

export function useLogout() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: () => api<{ message: string }>('/auth/logout', { method: 'POST' }),
    onSettled: () => {
      // Alle Daten des bisherigen Nutzers vergessen, danach gilt: nicht angemeldet
      client.clear();
      client.setQueryData(meKey, null);
    },
  });
}

// Läuft irgendeine Anfrage später in eine abgelaufene Sitzung (401), gilt der Nutzer
// als abgemeldet; die geschützten Routen leiten dann zur Anmeldung.
export function createQueryClient() {
  const client: QueryClient = new QueryClient({
    queryCache: new QueryCache({
      onError: (error) => {
        if (error instanceof ApiError && error.status === 401) client.setQueryData(meKey, null);
      },
    }),
    defaultOptions: {
      queries: { retry: (count, error) => !(error instanceof ApiError && error.status < 500) && count < 2 },
    },
  });
  return client;
}
