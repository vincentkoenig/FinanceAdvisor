// Kleiner fetch-Wrapper für die Flask-API unter /api/v1.
// Die API antwortet bei Fehlern immer mit {"error": "...", "fields": {...}} auf Deutsch;
// beides landet in ApiError, damit Formulare die Meldung direkt anzeigen können.

export const API_PREFIX = '/api/v1';

export class ApiError extends Error {
  status: number;
  fields: Record<string, string>;

  constructor(status: number, message: string, fields: Record<string, string> = {}) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.fields = fields;
  }
}

type Options = { method?: 'GET' | 'POST' | 'PUT' | 'DELETE'; body?: unknown };

export async function api<T>(path: string, { method = 'GET', body }: Options = {}): Promise<T> {
  let response: Response;
  try {
    response = await fetch(API_PREFIX + path, {
      method,
      credentials: 'same-origin',
      headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    throw new ApiError(0, 'Keine Verbindung zum Server. Bitte prüfe deine Internetverbindung.');
  }

  const data = await response.json().catch(() => null);
  if (!response.ok) {
    const message = data?.error ?? `Unerwartete Antwort vom Server (${response.status})`;
    throw new ApiError(response.status, message, data?.fields ?? {});
  }
  return data as T;
}
