// Lädt noch (ruhiger Platzhalter in der Form des Inhalts), Fehler mit "Erneut versuchen", oder der Inhalt
import type { UseQueryResult } from '@tanstack/react-query';
import type { ReactNode } from 'react';

type Shape = 'lines' | 'figure' | 'chart';

const SHAPES: Record<Shape, string[]> = {
  // Breiten der Balken: Zeilen einer Liste, die große Zahl einer Leitkarte, ein Wertverlauf
  lines: ['line w-80', 'line w-60', 'line w-70'],
  figure: ['figure', 'line w-50'],
  chart: ['chart'],
};

export function Skeleton({ shape = 'lines' }: { shape?: Shape }) {
  return (
    <div className={`skeleton skeleton-${shape}`} role="status" aria-label="Lädt">
      {SHAPES[shape].map((cls, i) => <span key={i} className={cls} />)}
    </div>
  );
}

export function Loaded({ queries, shape, children }: { queries: UseQueryResult[]; shape?: Shape; children: () => ReactNode }) {
  const failed = queries.find((q) => q.isError);
  if (failed) {
    return (
      <div className="load-error" role="alert">
        <span>Konnte nicht geladen werden.</span>
        <button className="btn btn-sm" onClick={() => queries.forEach((q) => q.isError && q.refetch())}>Erneut versuchen</button>
      </div>
    );
  }
  if (queries.some((q) => q.isPending)) return <Skeleton shape={shape} />;
  return <>{children()}</>;
}
