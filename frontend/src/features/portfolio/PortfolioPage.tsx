// Portfolio. Frage der Seite: Wie hat sich mein Depot entwickelt?
// Oben der Depotwert als Leitfläche mit Wertverlauf und Zeitraum, daneben die Aufteilung nach
// Anlageart, darunter Reiter für Positionen, Transaktionen und Dividenden.
// Kaufen, Verkaufen, Watchlist und Sparpläne laufen bis zum nächsten Schritt über die bisherige Seite.
import { useState } from 'react';
import {
  type Dividend, type Trade, useDividends, usePortfolioHistory, usePositions, useTrades,
} from '../../api/overview';
import { Icon } from '../../components/Icon';
import { Loaded } from '../../components/Loaded';
import { ValueChart } from '../../components/ValueChart';
import { useIsPhone } from '../../components/Fold';
import { dayShort, eur, parseDay, pct, qty, tone } from '../../lib/format';
import { type PositionRow, portfolioTotals, positionRows, token } from '../home/model';
import {
  type Range, RANGES, type Slice, type Sort, type SortKey,
  allocation, dividendsThisYear, finding, rangeChange, rangeSeries, sortRows,
} from './model';

// Bearbeiten läuft bis Portfolio II über die bisherige Seite
const LEGACY_PORTFOLIO = '/portfolio-page';

type AllocView = 'bar' | 'ring';
const ALLOC_KEY = 'ft-alloc-view';

function storedAllocView(): AllocView {
  try {
    return localStorage.getItem(ALLOC_KEY) === 'ring' ? 'ring' : 'bar';
  } catch {
    return 'bar';
  }
}

const TABS = [
  { id: 'positions', label: 'Positionen' },
  { id: 'trades', label: 'Transaktionen' },
  { id: 'dividends', label: 'Dividenden' },
] as const;
type Tab = (typeof TABS)[number]['id'];

// Dividenden je Anteil haben oft mehr als zwei Nachkommastellen
const perShareDigits = (value: number) => (Number(value.toFixed(2)) === value ? 2 : 4);

const dayNumeric = (iso: string) => parseDay(iso).toLocaleDateString('de-DE', { day: '2-digit', month: '2-digit', year: 'numeric' });

export function PortfolioPage() {
  const positions = usePositions();
  const history = usePortfolioHistory();
  const trades = useTrades();
  const dividends = useDividends();
  const [range, setRange] = useState<Range>('1M');
  const [allocView, setAllocViewState] = useState<AllocView>(storedAllocView);
  const [tab, setTab] = useState<Tab>('positions');
  const phone = useIsPhone();
  const today = new Date();

  const setAllocView = (view: AllocView) => {
    setAllocViewState(view);
    try { localStorage.setItem(ALLOC_KEY, view); } catch { /* nur eine Bequemlichkeit */ }
  };

  const rows = positions.data ? positionRows(positions.data) : null;
  const totals = positions.data ? portfolioTotals(positions.data) : null;
  const series = history.data && totals ? rangeSeries(history.data, range, today, totals.value) : null;
  const change = series && trades.data ? rangeChange(series, trades.data) : null;
  const found = rows ? finding(rows) : null;
  const counts: Record<Tab, number | undefined> = {
    positions: positions.data?.length, trades: trades.data?.length, dividends: dividends.data?.length,
  };

  return (
    <>
      <div className="title-row">
        <div className="text">
          <h1>Portfolio</h1>
          <p className="sub">
            {found?.kind === 'gain' && found.top.gain > 0 && <>{found.top.name} trägt <span className="pos">{eur(found.top.gain, { sign: true })}</span> zu deinem Gewinn von {eur(found.total)} bei</>}
            {found?.kind === 'gain' && found.top.gain <= 0 && <>Seit Kauf unverändert</>}
            {found?.kind === 'loss' && <>Seit Kauf <span className="neg">{eur(found.total)}</span>, am meisten bei {found.top.name} mit {eur(found.top.gain)}</>}
            {rows && rows.length === 0 && <>Noch keine Positionen im Depot</>}
          </p>
        </div>
        <div className="actions">
          <a className="btn" href={LEGACY_PORTFOLIO}><Icon name="plus" size={16} />Kaufen und verwalten</a>
        </div>
      </div>

      <div className="grid grid-3">
        <section className="panel hero span-2" aria-labelledby="h-value">
          <div className="hero-head">
            <div className="grow">
              <h2 className="lead-label" id="h-value">Depotwert</h2>
              <Loaded queries={[positions]}>
                {() => (
                  <>
                    <div className="lead-figure">{eur(totals!.value)}</div>
                    <p className="lead-sub num">
                      {change
                        ? <><span className={tone(change.abs)}>{eur(change.abs, { sign: true })}{change.pct !== null && ` (${pct(change.pct)})`}</span> {RANGES.find((r) => r.key === range)!.words}</>
                        : history.isPending || trades.isPending ? 'Verlauf lädt …' : 'Noch kein Verlauf'}
                    </p>
                  </>
                )}
              </Loaded>
            </div>
            <div className="segmented" role="group" aria-label="Zeitraum">
              {RANGES.map((r) => (
                <button key={r.key} aria-pressed={range === r.key} onClick={() => setRange(r.key)}>{r.key}</button>
              ))}
            </div>
          </div>
          <div className="chart-slot">
            <Loaded queries={[history, positions]}>
              {() => series!.length >= 2
                ? <ValueChart points={series!} height={phone ? 200 : 240} />
                : <p className="empty-line">Der Wertverlauf erscheint, sobald dein Depot einen Tag alt ist.</p>}
            </Loaded>
          </div>
        </section>

        <section className="panel" aria-labelledby="h-alloc">
          <div className="panel-head">
            <h2 id="h-alloc">Aufteilung</h2>
            <div className="segmented" role="group" aria-label="Darstellung">
              <button aria-pressed={allocView === 'bar'} onClick={() => setAllocView('bar')} aria-label="Als Balken" title="Als Balken"><Icon name="bars" size={16} /></button>
              <button aria-pressed={allocView === 'ring'} onClick={() => setAllocView('ring')} aria-label="Als Ring" title="Als Ring"><Icon name="ring" size={16} /></button>
            </div>
          </div>
          <Loaded queries={[positions]}>
            {() => {
              const slices = allocation(rows!);
              if (slices.length === 0) return <p className="empty-line">Die Aufteilung erscheint mit der ersten Position.</p>;
              return (
                <>
                  <Allocation slices={slices} view={allocView} total={totals!.value} />
                  {allocView === 'bar' && (
                    <div className="strip">
                      <div>
                        <div className="kpi-label">Einstand</div>
                        <div className="kpi-value kpi-small">{eur(totals!.cost, { digits: 0 })}</div>
                      </div>
                      <div>
                        <div className="kpi-label">Gewinn</div>
                        <div className={`kpi-value kpi-small ${tone(totals!.gain)}`}>{eur(totals!.gain, { sign: true, digits: 0 })}</div>
                        {totals!.gainPct !== null && <div className="kpi-sub">{pct(totals!.gainPct)}</div>}
                      </div>
                    </div>
                  )}
                </>
              );
            }}
          </Loaded>
        </section>
      </div>

      <div className="tabs" role="tablist" aria-label="Bereiche">
        {TABS.map((t) => (
          <button key={t.id} role="tab" id={`tab-${t.id}`} aria-controls="tab-panel" aria-selected={tab === t.id} onClick={() => setTab(t.id)}>
            {t.label}{counts[t.id] !== undefined && <span className="count">{counts[t.id]}</span>}
          </button>
        ))}
      </div>
      <section className="panel" role="tabpanel" id="tab-panel" aria-labelledby={`tab-${tab}`}>
        {tab === 'positions' && (
          <Loaded queries={[positions]}>
            {() => <Positions rows={rows!} />}
          </Loaded>
        )}
        {tab === 'trades' && (
          <Loaded queries={[trades]}>
            {() => <Trades trades={trades.data!} />}
          </Loaded>
        )}
        {tab === 'dividends' && (
          <Loaded queries={[dividends]}>
            {() => <Dividends dividends={dividends.data!} total={dividendsThisYear(dividends.data!, today)} year={today.getFullYear()} />}
          </Loaded>
        )}
      </section>
    </>
  );
}

function Allocation({ slices, view, total }: { slices: Slice[]; view: AllocView; total: number }) {
  const label = slices.map((s) => `${s.label} ${Math.round(s.share)} %`).join(', ');
  let chart;
  if (view === 'ring') {
    const r = 74, circumference = 2 * Math.PI * r, gap = slices.length > 1 ? 2.5 : 0;
    // Jedes Segment beginnt dort, wo die vorigen zusammen enden
    const lengths = slices.map((s) => (s.share / 100) * circumference);
    const starts = lengths.map((_, i) => lengths.slice(0, i).reduce((sum, l) => sum + l, 0));
    chart = (
      <div className="alloc-ring">
        <svg viewBox="0 0 176 176" role="img" aria-label={label}>
          <g transform="rotate(-90 88 88)">
            {slices.map((s, i) => (
              <circle key={s.key} cx="88" cy="88" r={r} fill="none" stroke={s.color} strokeWidth="12"
                strokeDasharray={`${Math.max(0, lengths[i] - gap).toFixed(2)} ${circumference.toFixed(2)}`} strokeDashoffset={(-starts[i]).toFixed(2)} />
            ))}
          </g>
        </svg>
        <div className="center"><span className="muted small">Depot</span><span className="figure">{eur(total, { digits: 0 })}</span></div>
      </div>
    );
  } else {
    chart = (
      <div className="alloc-bar" role="img" aria-label={label}>
        {slices.map((s) => <span key={s.key} style={{ flex: s.share, background: s.color }} />)}
      </div>
    );
  }
  return (
    <div className="alloc">
      {chart}
      <table className="legend-table num">
        <tbody>
          {slices.map((s) => (
            <tr key={s.key}>
              <td><span className="dot" style={{ background: s.color }} />{s.label}</td>
              <td className="r">{eur(s.value, { digits: 0 })}</td>
              <td className="r muted pct-col">{Math.round(s.share)} %</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

const COLUMNS: { key: SortKey; label: string; right?: boolean }[] = [
  { key: 'name', label: 'Titel' },
  { key: 'quantity', label: 'Stück', right: true },
  { key: 'price', label: 'Kurs', right: true },
  { key: 'value', label: 'Wert', right: true },
  { key: 'gain', label: 'Gewinn / Verlust', right: true },
];

function Positions({ rows }: { rows: PositionRow[] }) {
  const [sort, setSort] = useState<Sort>({ key: 'value', dir: -1 });
  if (rows.length === 0) {
    return <p className="empty-line">Noch keine Positionen. Über „Kaufen und verwalten“ legst du die erste an.</p>;
  }
  const sorted = sortRows(rows, sort);
  const value = rows.reduce((sum, row) => sum + row.value, 0);
  const gain = rows.reduce((sum, row) => sum + row.gain, 0);
  // Zahlen zuerst absteigend, Namen zuerst A–Z; ein zweiter Klick dreht die Richtung
  const sortBy = (key: SortKey) => setSort((s) => (s.key === key ? { key, dir: s.dir === 1 ? -1 : 1 } : { key, dir: key === 'name' ? 1 : -1 }));

  return (
    <>
      <div className="table-wrap desktop-only">
        <table className="table">
          <thead>
            <tr>
              {COLUMNS.map((c) => (
                <th key={c.key} className={c.right ? 'r' : undefined}
                  aria-sort={sort.key === c.key ? (sort.dir < 0 ? 'descending' : 'ascending') : 'none'}>
                  <button onClick={() => sortBy(c.key)}>
                    {c.label}{sort.key === c.key && <span aria-hidden="true">{sort.dir < 0 ? ' ↓' : ' ↑'}</span>}
                  </button>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {sorted.map((p) => (
              <tr key={p.asset_id}>
                <td>
                  <div className="ident">
                    <span className="token" aria-hidden="true">{token(p.symbol, p.name)}</span>
                    <div className="min0"><span className="name trunc">{p.name}</span><span className="sub-line">{p.symbol}</span></div>
                  </div>
                </td>
                <td className="r">{qty(p.quantity)}</td>
                <td className="r">{eur(p.price)}<span className="sub-line">Ø {eur(p.avg_buy_price)}</span></td>
                <td className="r strong">{eur(p.value)}<span className="sub-line">Einstand {eur(p.cost)}</span></td>
                <td className="r"><span className={tone(p.gain)}>{eur(p.gain, { sign: true })}</span><span className="sub-line">{p.gainPct === null ? '–' : pct(p.gainPct)}</span></td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr><td>Gesamt</td><td /><td /><td className="r">{eur(value)}</td><td className="r"><span className={tone(gain)}>{eur(gain, { sign: true })}</span></td></tr>
          </tfoot>
        </table>
      </div>

      <div className="only-phone">
        <div className="sort-row">
          <label className="muted" htmlFor="position-sort">Sortieren nach</label>
          <select className="select" id="position-sort" value={sort.key}
            onChange={(e) => { const key = e.target.value as SortKey; setSort({ key, dir: key === 'name' ? 1 : -1 }); }}>
            <option value="value">Wert</option>
            <option value="gain">Gewinn / Verlust</option>
            <option value="name">Name</option>
          </select>
        </div>
        <div className="rows">
          {sorted.map((p) => (
            <div className="row" key={p.asset_id}>
              <span className="token" aria-hidden="true">{token(p.symbol, p.name)}</span>
              <div className="grow"><span className="trunc">{p.name}</span><span className="sub-line">{qty(p.quantity)} Stück · {p.symbol}</span></div>
              <div className="end"><span className="strong">{eur(p.value)}</span><span className={`sub-line ${tone(p.gain)}`}>{p.gainPct === null ? '–' : pct(p.gainPct)} seit Kauf</span></div>
            </div>
          ))}
        </div>
      </div>
    </>
  );
}

function Trades({ trades }: { trades: Trade[] }) {
  if (trades.length === 0) return <p className="empty-line">Noch keine Käufe oder Verkäufe.</p>;
  const kind = (t: Trade) => (t.type === 'buy' ? 'Kauf' : 'Verkauf');
  return (
    <>
      <div className="table-wrap desktop-only">
        <table className="table">
          <thead>
            <tr><th>Datum</th><th>Titel</th><th>Art</th><th className="r">Stück</th><th className="r">Preis</th><th className="r">Betrag</th></tr>
          </thead>
          <tbody>
            {trades.map((t) => (
              <tr key={t.id}>
                <td className="muted">{dayNumeric(t.date)}</td>
                <td>{t.asset_name}</td>
                <td><span className="pill">{kind(t)}</span></td>
                <td className="r">{qty(t.quantity)}</td>
                <td className="r">{eur(t.price)}</td>
                <td className="r strong">{eur(t.total)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="rows only-phone">
        {trades.map((t) => (
          <div className="row" key={t.id}>
            <div className="grow"><span className="trunc">{t.asset_name}</span><span className="sub-line">{kind(t)} · {dayShort(t.date)} · {qty(t.quantity)} Stück</span></div>
            <div className="end strong">{eur(t.type === 'buy' ? t.total : -t.total, { sign: t.type === 'sell' })}</div>
          </div>
        ))}
      </div>
    </>
  );
}

function Dividends({ dividends, total, year }: { dividends: Dividend[]; total: number; year: number }) {
  return (
    <>
      <div className="panel-head">
        <h2>Dividenden</h2>
        <span className="meta num">{eur(total)} im Jahr {year}</span>
      </div>
      {dividends.length === 0
        ? <p className="empty-line">Noch keine Dividenden. Sie werden automatisch verbucht, sobald eine Position ausschüttet.</p>
        : (
          <>
            <div className="table-wrap desktop-only">
              <table className="table">
                <thead>
                  <tr><th>Ex-Tag</th><th>Titel</th><th className="r">Je Anteil</th><th className="r">Stück</th><th className="r">Betrag</th></tr>
                </thead>
                <tbody>
                  {dividends.map((d) => (
                    <tr key={d.id}>
                      <td className="muted">{dayNumeric(d.ex_dividend_date)}</td>
                      <td>{d.asset_name}</td>
                      <td className="r">{eur(d.amount_per_share, { digits: perShareDigits(d.amount_per_share) })}</td>
                      <td className="r">{qty(d.shares_held)}</td>
                      <td className="r pos strong">{eur(d.total_amount, { sign: true })}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="rows only-phone">
              {dividends.map((d) => (
                <div className="row" key={d.id}>
                  <div className="grow"><span className="trunc">{d.asset_name}</span><span className="sub-line">{dayShort(d.ex_dividend_date)} · {qty(d.shares_held)} Stück</span></div>
                  <div className="end pos">{eur(d.total_amount, { sign: true })}</div>
                </div>
              ))}
            </div>
          </>
        )}
    </>
  );
}
