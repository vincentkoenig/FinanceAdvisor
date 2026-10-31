// Wertverlauf als Linie mit leichter Fläche, wie Charts.line im Prototyp: 4 ruhige Gitterlinien mit
// runden Werten, 2px-Linie ohne Punkte, beim Zeigen eine senkrechte Linie mit schlichtem Tooltip.
// Farben aus den Tokens, damit die Linie auch auf der grünen Leitfläche passt. Käufe und Verkäufe
// sitzen auf der Linie und stehen im Tooltip: Kauf als gefüllter Punkt, Verkauf als Ring (auch ohne
// Farbe unterscheidbar), an Tagen mit beidem der Punkt im Ring.
import { useEffect, useRef, useState, type PointerEvent } from 'react';
import type { HistoryPoint, Trade } from '../api/overview';
import { niceTicks, type TradeMark } from '../features/portfolio/model';
import { eur, parseDay } from '../lib/format';
import { MASK, useMoney, usePrivacy } from '../lib/privacy';

const PAD_TOP = 8;
const PAD_BOTTOM = 26;
const decimal = new Intl.NumberFormat('de-DE', { maximumFractionDigits: 1 });

function tickLabel(value: number, hidden: boolean) {
  if (hidden) return MASK;
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

function tradeWord(trades: Trade[]) {
  const buys = trades.filter((t) => t.type === 'buy').length;
  const sells = trades.length - buys;
  return [buys && `${buys} ${buys === 1 ? 'Kauf' : 'Käufe'}`, sells && `${sells} ${sells === 1 ? 'Verkauf' : 'Verkäufe'}`]
    .filter(Boolean).join(' und ');
}

type Props = { points: HistoryPoint[]; marks?: TradeMark[]; height?: number };

export function ValueChart({ points, marks = [], height = 240 }: Props) {
  const [ref, width] = useWidth(600);
  const [hover, setHover] = useState<number | null>(null);
  const { hidden } = usePrivacy();
  const { qty } = useMoney();
  const money = (value: number) => (hidden ? `${MASK} €` : eur(value));

  const values = points.map((p) => p.value);
  const lowest = Math.min(...values);
  // Eine Wertlinie braucht keine Null-Basis: die Skala beginnt knapp unter dem tiefsten Wert
  const ticks = niceTicks(lowest * 0.97, Math.max(...values), 4);
  const bottom = ticks[0], top = ticks[ticks.length - 1];
  const padLeft = 12 + Math.max(...ticks.map((t) => tickLabel(t, hidden).length)) * 6.6;
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
  const allTrades = marks.flatMap((m) => m.trades);
  const label = `Depotwert vom ${dayLong(first.date)} bis ${dayLong(last.date)}, zuletzt ${money(last.value)}`
    + (allTrades.length ? `, ${tradeWord(allTrades)} im Zeitraum` : '');
  const hovered = hover === null ? null : points[hover];
  const hoveredTrades = marks.find((m) => m.index === hover)?.trades ?? [];

  return (
    <div className="value-chart" ref={ref}>
      <svg viewBox={`0 0 ${width} ${height}`} width="100%" height={height} role="img" aria-label={label}>
        {ticks.map((t) => (
          <g key={t}>
            <line x1={padLeft} x2={width} y1={y(t)} y2={y(t)} className="grid" shapeRendering="crispEdges" />
            <text x={padLeft - 8} y={y(t) + 4} textAnchor="end" className="axis">{tickLabel(t, hidden)}</text>
          </g>
        ))}
        {xTicks.map((i) => (
          <text key={i} x={x(i)} y={height - PAD_BOTTOM + 18} className="axis"
            textAnchor={i === 0 ? 'start' : i === points.length - 1 ? 'end' : 'middle'}>{xLabel(points[i].date)}</text>
        ))}
        <path d={area} className="area" />
        <path d={line} className="line" />
        {marks.map(({ index, trades }) => {
          const buy = trades.some((t) => t.type === 'buy'), sell = trades.some((t) => t.type === 'sell');
          const cx = x(index), cy = y(points[index].value);
          return (
            <g key={index} className="trade-mark">
              {sell && <circle cx={cx} cy={cy} r={buy ? 7 : 5} className="trade-sell" />}
              {buy && <circle cx={cx} cy={cy} r={sell ? 3.5 : 4.5} className="trade-buy" />}
            </g>
          );
        })}
        {hovered && (
          <>
            <line x1={x(hover!)} x2={x(hover!)} y1={PAD_TOP} y2={height - PAD_BOTTOM} className="rule" />
            <circle cx={x(hover!)} cy={y(hovered.value)} r={3.5} className="dot-mark" />
          </>
        )}
        {/* etwas über den letzten Punkt hinaus, damit er sich am Rand gut treffen lässt */}
        <rect x={padLeft} y={PAD_TOP} width={plotWidth + 12} height={height - PAD_TOP - PAD_BOTTOM} fill="transparent"
          onPointerMove={onMove} onPointerDown={onMove} onPointerLeave={() => setHover(null)} />
      </svg>
      {hovered && (
        // Rechts von der Linie, in der rechten Hälfte links davon, damit er nie über den Rand ragt
        <div className="chart-tip" aria-hidden="true" style={{
          left: `${(x(hover!) / width) * 100}%`,
          transform: x(hover!) > width * 0.6 ? 'translateX(calc(-100% - 12px))' : 'translateX(12px)',
        }}>
          <div className="muted">{dayLong(hovered.date)}</div>
          <b>{money(hovered.value)}</b>
          {hoveredTrades.map((t) => (
            <div key={t.id} className={`tip-trade trade-${t.type}`}>
              {t.type === 'buy' ? 'Kauf' : 'Verkauf'} {t.asset_symbol || t.asset_name} · {qty(t.quantity)} Stück · {money(t.total)}
            </div>
          ))}
        </div>
      )}
      {marks.length > 0 && (
        <p className="chart-legend" aria-hidden="true">
          <span><i className="trade-buy" />Kauf</span><span><i className="trade-sell" />Verkauf</span>
        </p>
      )}
    </div>
  );
}
