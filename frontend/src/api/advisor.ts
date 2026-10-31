// KI-Berater: Chatverlauf, neue Nachricht, Portfolio-Analysen.
// Beides ruft ein Sprachmodell auf und kann einige Sekunden dauern; die API begrenzt die Anzahl pro Stunde.
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from './client';

export type ChatEntry = { role: 'user' | 'assistant'; message: string };

export type Analysis = {
  id: number;
  total_value: number;
  risk_assessment: string;
  diversification_score: number | null;
  summary: string;
  recommendations: string[];
  created_at: string; // "31.10.2026 09:15"
};

export const advisorKeys = {
  chat: ['chat-history'] as const,
  analyses: ['analyses'] as const,
};

export const useChatHistory = () =>
  useQuery({ queryKey: advisorKeys.chat, queryFn: () => api<ChatEntry[]>('/me/chat/history'), staleTime: Infinity });

// Nach der Antwort kommen Frage und Antwort direkt in den Verlauf, ohne ihn neu zu laden
export function useSendMessage() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (message: string) => api<{ reply: string }>('/me/chat', { method: 'POST', body: { message } }),
    onSuccess: ({ reply }, message) => client.setQueryData<ChatEntry[]>(advisorKeys.chat, (old = []) => [
      ...old, { role: 'user', message }, { role: 'assistant', message: reply },
    ]),
  });
}

export const useAnalyses = () =>
  useQuery({ queryKey: advisorKeys.analyses, queryFn: () => api<Analysis[]>('/me/analyses'), staleTime: 10 * 60_000 });

export function useRunAnalysis() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: () => api<{ disclaimer?: string }>('/me/analyses', { method: 'POST', body: {} }),
    onSuccess: () => client.invalidateQueries({ queryKey: advisorKeys.analyses }),
  });
}
