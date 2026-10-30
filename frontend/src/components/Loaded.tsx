// Lädt noch, Fehler mit "Erneut versuchen", oder der Inhalt
import type { UseQueryResult } from '@tanstack/react-query';
import type { ReactNode } from 'react';

export function Loaded({ queries, children }: { queries: UseQueryResult[]; children: () => ReactNode }) {
  const failed = queries.find((q) => q.isError);
  if (failed) {
    return (
      <div className="load-error" role="alert">
        <span>Konnte nicht geladen werden.</span>
        <button className="btn btn-sm" onClick={() => queries.forEach((q) => q.isError && q.refetch())}>Erneut versuchen</button>
      </div>
    );
  }
  if (queries.some((q) => q.isPending)) return <p className="muted loading" role="status">Lädt …</p>;
  return <>{children()}</>;
}
