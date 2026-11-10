// Rendite des Depots neben dem Vergleichsindex, beide in Prozent ab dem Ausgangstag. Gleiche Bauweise
// wie ValueChart: ruhige Gitterlinien mit runden Werten, die Nulllinie etwas kräftiger, das Depot als
// 2px-Linie mit leichter Fläche bis zur Null, der Index gestrichelt (auch ohne Farbe unterscheidbar).
// Beim Zeigen eine senkrechte Linie mit beiden Werten im Tooltip.
import { useState, type PointerEvent } from 'react';
import { niceTicks, type ReturnPoint } from '../features/portfolio/model';
import { parseDay, pct } from '../lib/format';
import { useWidth } from './ValueChart';

const PAD_TOP = 8;
const PAD_BOTTOM = 26;

function dayLong(iso: string) {
  return parseDay(iso).toLocaleDateString('de-DE', { day: 'numeric', month: 'short', year: 'numeric' });
}

const axisPct = (v: number) => `${v > 0 ? '+' : v < 0 ? '−' : ''}${new Intl.NumberFormat('de-DE', { maximumFractionDigits: 1 }).format(Math.abs(v))} %`;

type Props = { points: ReturnPoint[]; benchmarkName: string | null; height?: number };

export function ReturnChart({ points, benchmarkName, height = 240 }: Props) {
  const [ref, width] = useWidth(600);
  const [hover, setHover] = useState<number | null>(null);

  const values = points.flatMap((p) => (p.benchmark === null ? [p.portfolio] : [p.portfolio, p.benchmark]));
  const ticks = niceTicks(Math.min(0, ...values), Math.max(0, ...values), 4);
  const bottom = ticks[0], top = ticks[ticks.length - 1];
  const padLeft = 12 + Math.max(...ticks.map((t) => axisPct(t).length)) * 6.6;
  const plotWidth = width - padLeft;
  const x = (i: number) => padLeft + (i * plotWidth) / Math.max(1, points.length - 1);
  const y = (v: number) => PAD_TOP + (height - PAD_TOP - PAD_BOTTOM) * (1 - (v - bottom) / (top - bottom));

  const path = (get: (p: ReturnPoint) => number | null) => {
    let d = '', open = false;
    points.forEach((p, i) => {
      const v = get(p);
      if (v === null) { open = false; return; }
      d += `${open ? 'L' : 'M'}${x(i).toFixed(1)} ${y(v).toFixed(1)}`;
      open = true;
    });
    return d;
  };
  const depot = path((p) => p.portfolio);
  const bench = benchmarkName ? path((p) => p.benchmark) : '';
  const area = `${depot}L${x(points.length - 1).toFixed(1)} ${y(0)}L${x(0).toFixed(1)} ${y(0)}Z`;

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
  const label = `Rendite vom ${dayLong(first.date)} bis ${dayLong(last.date)}: Depot ${pct(last.portfolio)}`
    + (benchmarkName && last.benchmark !== null ? `, ${benchmarkName} ${pct(last.benchmark)}` : '');
  const hovered = hover === null ? null : points[hover];

  return (
    <div className="value-chart return-chart" ref={ref}>
      <svg viewBox={`0 0 ${width} ${height}`} width="100%" height={height} role="img" aria-label={label}>
        {ticks.map((t) => (
          <g key={t}>
            <line x1={padLeft} x2={width} y1={y(t)} y2={y(t)} className={t === 0 ? 'grid zero' : 'grid'} shapeRendering="crispEdges" />
            <text x={padLeft - 8} y={y(t) + 4} textAnchor="end" className="axis">{axisPct(t)}</text>
          </g>
        ))}
        {xTicks.map((i) => (
          <text key={i} x={x(i)} y={height - PAD_BOTTOM + 18} className="axis"
            textAnchor={i === 0 ? 'start' : i === points.length - 1 ? 'end' : 'middle'}>{xLabel(points[i].date)}</text>
        ))}
        <path d={area} className="area" />
        {bench && <path d={bench} className="bench" />}
        <path d={depot} className="line" />
        {hovered && (
          <>
            <line x1={x(hover!)} x2={x(hover!)} y1={PAD_TOP} y2={height - PAD_BOTTOM} className="rule" />
            <circle cx={x(hover!)} cy={y(hovered.portfolio)} r={3.5} className="dot-mark" />
          </>
        )}
        <rect x={padLeft} y={PAD_TOP} width={plotWidth + 12} height={height - PAD_TOP - PAD_BOTTOM} fill="transparent"
          onPointerMove={onMove} onPointerDown={onMove} onPointerLeave={() => setHover(null)} />
      </svg>
      {hovered && (
        <div className="chart-tip" aria-hidden="true" style={{
          left: `${(x(hover!) / width) * 100}%`,
          transform: x(hover!) > width * 0.6 ? 'translateX(calc(-100% - 12px))' : 'translateX(12px)',
        }}>
          <div className="muted">{dayLong(hovered.date)}</div>
          <div>Depot <b>{pct(hovered.portfolio)}</b></div>
          {benchmarkName && hovered.benchmark !== null && <div>{benchmarkName} <b>{pct(hovered.benchmark)}</b></div>}
        </div>
      )}
      <p className="chart-legend" aria-hidden="true">
        <span><i className="key-depot" />Dein Depot</span>
        {benchmarkName && <span><i className="key-bench" />{benchmarkName}</span>}
      </p>
    </div>
  );
}
