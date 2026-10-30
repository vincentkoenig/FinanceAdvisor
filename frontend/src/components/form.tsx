// Bausteine für Formulare in Dialogen: Feld mit Meldung, Prüfung von Beträgen, Fehler der API, Knöpfe.
import type { ReactNode } from 'react';
import { ApiError } from '../api/client';
import { parseAmount } from '../lib/format';

export type Errors = Record<string, string>;

// Fehler der API: Feldfehler an die Felder, alles andere als Meldung über den Knöpfen
export function apiErrors(error: unknown, fieldNames: Record<string, string>): Errors {
  if (error instanceof ApiError) {
    const errors: Errors = {};
    for (const [field, message] of Object.entries(error.fields)) errors[fieldNames[field] ?? 'form'] = message;
    if (Object.keys(errors).length === 0) errors.form = error.message;
    return errors;
  }
  return { form: 'Das hat nicht geklappt. Bitte versuche es noch einmal.' };
}

export function positive(text: string, label: string, errors: Errors, key: string) {
  const value = parseAmount(text);
  if (value === null || Number.isNaN(value) || value <= 0) {
    errors[key] = `Bitte ${label} größer 0 eingeben.`;
    return 0;
  }
  return value;
}

export function Field({ id, label, error, hint, children }: { id: string; label: string; error?: string; hint?: string; children: ReactNode }) {
  return (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      {children}
      {error ? <p className="err" id={`${id}-msg`}>{error}</p> : hint && <p className="hint" id={`${id}-msg`}>{hint}</p>}
    </div>
  );
}

// Verknüpft das Feld mit seiner Meldung oder seinem Hinweis
export const describe = (id: string, error?: string, hasHint = false) =>
  ({ 'aria-invalid': error ? true : undefined, 'aria-describedby': error || hasHint ? `${id}-msg` : undefined });

export function Actions({ onCancel, busy, label, busyLabel, error }: { onCancel: () => void; busy: boolean; label: string; busyLabel: string; error?: string }) {
  return (
    <>
      {error && <p className="err" role="alert">{error}</p>}
      <div className="dialog-actions">
        <button type="button" className="btn" onClick={onCancel} disabled={busy}>Abbrechen</button>
        <button type="submit" className="btn btn-primary" disabled={busy}>{busy ? busyLabel : label}</button>
      </div>
    </>
  );
}
