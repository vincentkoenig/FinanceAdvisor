// Wöchentliche Einschätzungen des Analysten (Sonntag 18 Uhr, analyst/service.py).
import { useQuery } from '@tanstack/react-query';
import { api } from './client';

export type AnalystItem = {
  asset_id: number;
  name: string;
  symbol: string;
  kind: 'position' | 'watchlist';
  stance: string;
  stance_label: string;
  confidence: 'niedrig' | 'mittel' | 'hoch';
  reasoning: string;
  invalidation: string;
  price: number;
  indicators: {
    trend: 'up' | 'down' | 'sideways' | null;
    pullback: boolean; overheated: boolean; trend_break: boolean;
    rsi14: number | null; above_sma200_pct: number | null; from_high_pct: number | null; sma200: number | null;
  };
  previous_label: string | null;
  changed: boolean;
};

export type AnalystRun = { run_date: string | null; model: string; items: AnalystItem[] };

export const useAnalyst = () =>
  useQuery({ queryKey: ['analyst'], queryFn: () => api<AnalystRun>('/me/analyst'), staleTime: 30 * 60 * 1000 });

/** Auswertung einer Gruppe von Einschätzungen nach 30 bzw. 90 Tagen */
export type TrackSummary = {
  evaluated: number; scored: number; hits: number;
  hit_rate: number | null; avg_change: number | null; avg_benchmark: number | null;
};

export type TrackRecord = {
  benchmark: string;
  signals: number;
  first_result_on: string | null;
  horizons: Record<'30' | '90', TrackSummary>;
  by_stance: { stance: string; stance_label: string; direction: 'up' | 'down' | null; horizons: Record<'30' | '90', TrackSummary> }[];
};

export const useTrackRecord = () =>
  useQuery({ queryKey: ['analyst', 'track-record'], queryFn: () => api<TrackRecord>('/me/analyst/track-record'), staleTime: 30 * 60 * 1000 });
