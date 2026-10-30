// Wertverlauf als Linie mit leichter Fläche, wie Charts.line im Prototyp: 4 ruhige Gitterlinien mit
// runden Werten, 2px-Linie ohne Punkte, beim Zeigen eine senkrechte Linie mit schlichtem Tooltip.
// Farben aus den Tokens, damit die Linie auch auf der grünen Leitfläche passt.
import { useEffect, useRef, useState, type PointerEvent } from 'react';
import type { HistoryPoint } from '../api/overview';
import { niceTicks } from '../features/portfolio/model';
import { eur, parseDay } from '../lib/format';

const PAD_TOP = 8;
const PAD_BOTTOM = 26;
const decimal = new Intl.NumberFormat('de-DE', { maximumFractionDigits: 1 });

function tickLabel(value: number) {
  return Math.abs(value) >= 1000 ? `${decimal.format(value / 1000)} Tsd.` : eur(value, { digits: 0 });
}

function dayLong(iso: string) {
  return parseDay(iso).toLocaleDateString('de-DE', { day: 'numeric', month: 'short', year: 'numeric' });
}

// Breite des Behälters; jsdom kennt keinen ResizeObserver, dann bleibt es bei der Vorgabe
function useWidth(fallback: number) {
  const ref = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(fallback);
  useEffect(() => {
    const el = ref.current;
    if (!el || typeof ResizeObserver === 'undefined') return;
    const observer = new ResizeObserver(([entry]) => setWidth(Math.max(240, Math.round(entry.contentRect.width))));
    observer.observe(el);
    return () => observer.disconnect();
  }, []);
  return [ref, width] as const;
}

export function ValueChart({ points, height = 240 }: { points: HistoryPoint[]; height?: number }) {
  const [ref, width] = useWidth(600);
  const [hover, setHover] = useState<number | null>(null);

  const values = points.map((p) => p.value);
  const lowest = Math.min(...values);
  // Eine Wertlinie braucht keine Null-Basis: die Skala beginnt knapp unter dem tiefsten Wert
  const ticks = niceTicks(lowest * 0.97, Math.max(...values), 4);
  const bottom = ticks[0], top = ticks[ticks.length - 1];
  const padLeft = 12 + Math.max(...ticks.map((t) => tickLabel(t).length)) * 6.6;
  const plotWidth = width - padLeft;
  const x = (i: number) => padLeft + (i * plotWidth) / Math.max(1, points.length - 1);
  const y = (v: number) => PAD_TOP + (height - PAD_TOP - PAD_BOTTOM) * (1 - (v - bottom) / (top - bottom));

  const line = points.map((p, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)} ${y(p.value).toFixed(1)}`).join('');
  const area = `${line}L${x(points.length - 1).toFixed(1)} ${y(bottom)}L${x(0).toFixed(1)} ${y(bottom)}Z`;

  // Datumsbeschriftungen in gleichem Abstand, so viele wie in die Breite passen
  const long = points.length > 40;
  const xLabel = (iso: string) => parseDay(iso).toLocaleDateString('de-DE', long ? { month: 'short', year: '2-digit' } : { day: 'numeric', month: 'short' });
  const fits = Math.max(2, Math.floor(plotWidth / 84));
  const every = Math.max(1, Math.ceil((points.length - 1) / (fits - 1)));
  const xTicks = points.map((_, i) => i).filter((i) => i % every === 0);

  const onMove = (event: PointerEvent<SVGRectElement>) => {
    const box = event.currentTarget.ownerSVGElement!.getBoundingClientRect();
    const px = ((event.clientX - box.left) / box.width) * width;
    setHover(Math.max(0, Math.min(points.length - 1, Math.round(((px - padLeft) / plotWidth) * (points.length - 1)))));
  };

  const first = points[0], last = points[points.length - 1];
  const label = `Depotwert vom ${dayLong(first.date)} bis ${dayLong(last.date)}, zuletzt ${eur(last.value)}`;
  const hovered = hover === null ? null : points[hover];

  return (
    <div className="value-chart" ref={ref}>
      <svg viewBox={`0 0 ${width} ${height}`} width="100%" height={height} role="img" aria-label={label}>
        {ticks.map((t) => (
          <g key={t}>
            <line x1={padLeft} x2={width} y1={y(t)} y2={y(t)} className="grid" shapeRendering="crispEdges" />
            <text x={padLeft - 8} y={y(t) + 4} textAnchor="end" className="axis">{tickLabel(t)}</text>
          </g>
        ))}
        {xTicks.map((i) => (
          <text key={i} x={x(i)} y={height - PAD_BOTTOM + 18} className="axis"
            textAnchor={i === 0 ? 'start' : i === points.length - 1 ? 'end' : 'middle'}>{xLabel(points[i].date)}</text>
        ))}
        <path d={area} className="area" />
        <path d={line} className="line" />
        {hovered && (
          <>
            <line x1={x(hover!)} x2={x(hover!)} y1={PAD_TOP} y2={height - PAD_BOTTOM} className="rule" />
            <circle cx={x(hover!)} cy={y(hovered.value)} r={3.5} className="dot-mark" />
          </>
        )}
        <rect x={padLeft} y={PAD_TOP} width={plotWidth} height={height - PAD_TOP - PAD_BOTTOM} fill="transparent"
          onPointerMove={onMove} onPointerDown={onMove} onPointerLeave={() => setHover(null)} />
      </svg>
      {hovered && (
        // Rechts von der Linie, in der rechten Hälfte links davon, damit er nie über den Rand ragt
        <div className="chart-tip" aria-hidden="true" style={{
          left: `${(x(hover!) / width) * 100}%`,
          transform: x(hover!) > width * 0.6 ? 'translateX(calc(-100% - 12px))' : 'translateX(12px)',
        }}>
          <div className="muted">{dayLong(hovered.date)}</div>
          <b>{eur(hovered.value)}</b>
        </div>
      )}
    </div>
  );
}
