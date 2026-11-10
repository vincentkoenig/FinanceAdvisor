// Heatmap der Positionen: die Fläche jeder Kachel ist ihr Anteil am Depot, die Farbe ihre Entwicklung
// (heute oder seit Kauf), Jade für Plus, Rostrot für Minus, kräftiger je größer die Bewegung. Ab der
// Kappungsgrenze bleibt die Farbe voll. Jede Kachel öffnet die Position wie eine Zeile der Tabelle.
// Die Kacheln sind Schaltflächen mit vollständigem Namen, damit die Karte auch ohne Farbe lesbar ist.
import { useState } from 'react';
import { useIsPhone } from '../../components/Fold';
import { useWidth } from '../../components/ValueChart';
import { pct } from '../../lib/format';
import { useMoney } from '../../lib/privacy';
import type { PositionRow } from '../home/model';
import { squarify } from './model';

type Mode = 'day' | 'total';
const MODE_KEY = 'ft-heat-mode';
// Ab dieser Bewegung (in Prozent) ist die Farbe voll
const CAP: Record<Mode, number> = { day: 3, total: 25 };
const GAP = 4;

function storedMode(): Mode {
  try {
    return localStorage.getItem(MODE_KEY) === 'total' ? 'total' : 'day';
  } catch {
    return 'day';
  }
}

export function Heatmap({ rows, onOpen }: { rows: PositionRow[]; onOpen: (row: PositionRow) => void }) {
  const { eur } = useMoney();
  const [mode, setModeState] = useState<Mode>(storedMode);
  const [ref, width] = useWidth(800);
  const phone = useIsPhone();
  const height = phone ? 280 : 320;
  const total = rows.reduce((sum, row) => sum + row.value, 0);

  const setMode = (next: Mode) => {
    setModeState(next);
    try { localStorage.setItem(MODE_KEY, next); } catch { /* nur eine Bequemlichkeit */ }
  };

  const change = (row: PositionRow) => (mode === 'day' ? row.dayPct : row.gainPct);
  const tiles = squarify(rows.map((row) => ({ item: row, weight: row.value })), width, height);

  return (
    <section className="panel" aria-labelledby="h-heat">
      <div className="panel-head">
        <div>
          <h2 id="h-heat">Gewinner und Verlierer</h2>
          <p className="muted small">Fläche nach Anteil am Depot, Farbe nach Entwicklung</p>
        </div>
        <div className="segmented" role="group" aria-label="Entwicklung">
          <button aria-pressed={mode === 'day'} onClick={() => setMode('day')}>Heute</button>
          <button aria-pressed={mode === 'total'} onClick={() => setMode('total')}>Seit Kauf</button>
        </div>
      </div>
      <div className="heatmap" ref={ref} style={{ height }}>
        {tiles.map(({ item: row, x, y, w, h }) => {
          const value = change(row);
          const t = value === null ? 0 : Math.min(Math.abs(value) / CAP[mode], 1);
          const size = w < 64 || h < 48 ? 'dot' : w < 120 || h < 92 ? 'tiny' : '';
          const share = total > 0 ? (row.value / total) * 100 : 0;
          return (
            <button key={row.asset_id} type="button" className={`heat-tile ${size} ${value !== null && value < 0 ? 'down' : 'up'}`}
              style={{ left: x + GAP / 2, top: y + GAP / 2, width: w - GAP, height: h - GAP, ['--t' as string]: t.toFixed(3) }}
              aria-label={`${row.name}, ${mode === 'day' ? 'heute' : 'seit Kauf'} ${value === null ? 'ohne Kurs' : pct(value)}, ${eur(row.value)}, ${Math.round(share)} % vom Depot`}
              title={`${row.name}: ${value === null ? 'ohne Kurs' : pct(value)}`}
              onClick={() => onOpen(row)}>
              <span className="heat-top">
                <span className="heat-sym">{row.symbol && row.symbol !== '-' ? row.symbol.split(/[.\-=]/)[0] : row.name}</span>
                <span className="heat-name">{row.name}</span>
              </span>
              <span className="heat-bottom">
                <span className="heat-chg">{value === null ? '–' : pct(value)}</span>
                <span className="heat-val">{eur(row.value, { digits: 0 })} · {Math.round(share)} %</span>
              </span>
            </button>
          );
        })}
      </div>
      <div className="heat-scale" aria-hidden="true">
        <span>{pct(-CAP[mode])}</span><span className="ramp" /><span>{pct(CAP[mode])}</span>
      </div>
    </section>
  );
}
