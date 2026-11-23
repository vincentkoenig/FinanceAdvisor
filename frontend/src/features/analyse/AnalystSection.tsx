// Wöchentliche Einschätzungen des Analysten auf der Analyse-Seite: pro Depotposition und
// Watchlist-Wert eine Stufe mit Begründung, Zuversicht und der Marke, ab der sie nicht mehr gilt.
// Geändert gegenüber der Vorwoche wird markiert. Automatisch erzeugt, keine Anlageberatung.
import { type AnalystItem, type Fundamentals, type TrackSummary, useAnalyst, useTrackRecord } from '../../api/analyst';
import { Loaded } from '../../components/Loaded';
import { dayShort } from '../../lib/format';
import { useMoney } from '../../lib/privacy';
import './analyse.css';

const TREND: Record<string, string> = { up: 'Aufwärtstrend', down: 'Abwärtstrend', sideways: 'Seitwärts' };
// Stufen, die zum Handeln auffordern, bekommen die Signalfarbe
const ACTIVE = new Set(['add', 'take_profit', 'review_sale', 'entry']);

const pctText = (value: number) => `${Math.abs(value).toLocaleString('de-DE', { maximumFractionDigits: 0 })} %`;

function facts(item: AnalystItem) {
  const { trend, rsi14, above_sma200_pct: above, from_high_pct: fromHigh } = item.indicators;
  const parts = [trend ? TREND[trend] : 'Zu wenig Historie für einen Trend'];
  if (above !== null) parts.push(`${pctText(above)} ${above >= 0 ? 'über' : 'unter'} der 200-Tage-Linie`);
  if (fromHigh !== null && fromHigh < 0) parts.push(`${pctText(fromHigh)} unter dem Jahreshoch`);
  if (rsi14 !== null) parts.push(`RSI ${Math.round(rsi14)}`);
  return parts.join(' · ');
}

const num = (value: number) => value.toLocaleString('de-DE', { maximumFractionDigits: 1 });
const plus = (value: number) => `${value > 0 ? '+' : value < 0 ? '−' : ''}${num(Math.abs(value))} %`;

// Kurzfassung der Fundamentaldaten einer Aktie; was yfinance nicht liefert, fehlt
function fundamentalsLine(f: Fundamentals) {
  const parts: string[] = [];
  if (f.pe !== undefined) parts.push(`KGV ${num(f.pe)}${f.forward_pe !== undefined ? ` (erwartet ${num(f.forward_pe)})` : ''}`);
  if (f.revenue_growth_pct !== undefined) parts.push(`Umsatz ${plus(f.revenue_growth_pct)}`);
  if (f.earnings_growth_pct !== undefined) parts.push(`Gewinn ${plus(f.earnings_growth_pct)}`);
  if (f.profit_margin_pct !== undefined) parts.push(`Marge ${num(f.profit_margin_pct)} %`);
  if (f.recommendation) {
    const extra = [f.analysts !== undefined ? `${f.analysts}` : null, f.target_pct !== undefined ? `Kursziel ${plus(f.target_pct)}` : null].filter(Boolean);
    parts.push(`Analysten: ${f.recommendation}${extra.length ? ` (${extra.join(', ')})` : ''}`);
  }
  return parts.join(' · ');
}

function Signal({ item }: { item: AnalystItem }) {
  const { text } = useMoney();
  return (
    <details className="row older">
      <summary>
        <span className="grow">
          <span className="strong">{item.name}</span>
          <span className="sub-line">{item.symbol} · Zuversicht {item.confidence}</span>
        </span>
        <span className="end">
          <span className={`pill${ACTIVE.has(item.stance) ? ' pill-signal' : ''}`}>{item.stance_label}</span>
          {item.changed && <span className="sub-line">geändert, vorher {item.previous_label}</span>}
        </span>
      </summary>
      <div className="older-body">
        <p className="prose">{text(item.reasoning)}</p>
        <p className="prose"><span className="strong">Gilt nicht mehr, wenn:</span> {text(item.invalidation)}</p>
        <p className="hint">{facts(item)}</p>
        {item.indicators.fundamentals && fundamentalsLine(item.indicators.fundamentals) && (
          <p className="hint">{fundamentalsLine(item.indicators.fundamentals)}</p>
        )}
      </div>
    </details>
  );
}

function Group({ title, items }: { title: string; items: AnalystItem[] }) {
  if (!items.length) return null;
  return (
    <>
      <h3 className="sub-head">{title}</h3>
      <div className="rows">{items.map((item) => <Signal key={item.asset_id} item={item} />)}</div>
    </>
  );
}


function rate(summary: TrackSummary) {
  return summary.hit_rate === null ? '–' : `${summary.hit_rate} %`;
}

// Wie gut lag der Analyst? Treffer: Kaufen-Stufen gestiegen, Verkaufen-Stufen gefallen;
// Halten/Abwarten zählen nicht, für sie steht nur die Entwicklung da.
function TrackRecordPanel() {
  const record = useTrackRecord();
  return (
    <section className="track" aria-labelledby="h-track">
      <h3 id="h-track" className="sub-head">Trefferquote</h3>
      <Loaded queries={[record]}>
        {() => {
          const data = record.data!;
          if (!data.signals) return null;
          if (!data.horizons['30'].evaluated) {
            return <p className="hint">Die erste Auswertung gibt es ab {dayShort(data.first_result_on!)}, 30 Tage nach der ersten Einschätzung. Bis dahin sammelt FinTrack die Kurse.</p>;
          }
          return (
            <>
              <div className="strip well">
                {(['30', '90'] as const).map((h) => {
                  const s = data.horizons[h];
                  return (
                    <div key={h}>
                      <div className="kpi-label">Nach {h} Tagen</div>
                      <div className="kpi-value kpi-small">{s.evaluated ? rate(s) : '–'}</div>
                      <div className="kpi-sub">
                        {s.evaluated
                          ? <>{s.hits} von {s.scored} Treffern · Ø {plus(s.avg_change!)}{s.avg_benchmark !== null && <>, {data.benchmark} {plus(s.avg_benchmark)}</>}</>
                          : 'noch keine Auswertung'}
                      </div>
                    </div>
                  );
                })}
              </div>
              <div className="rows">
                {data.by_stance.filter((s) => s.horizons['30'].evaluated).map((s) => (
                  <div className="row" key={s.stance}>
                    <span className="grow"><span className="strong">{s.stance_label}</span>
                      <span className="sub-line">{s.direction ? `${s.horizons['30'].hits} von ${s.horizons['30'].scored} nach 30 Tagen` : 'ohne Richtung, zählt nicht zur Quote'}</span></span>
                    <span className="end">
                      <span className="strong block">{s.direction ? rate(s.horizons['30']) : plus(s.horizons['30'].avg_change!)}</span>
                      <span className="sub-line">{s.direction ? `Ø ${plus(s.horizons['30'].avg_change!)}` : 'Ø Entwicklung'}</span>
                    </span>
                  </div>
                ))}
              </div>
              <p className="hint">
                Treffer: Bei „Nachkaufen“ und „Einstieg interessant“ ist der Kurs gestiegen, bei „Teilgewinn“, „Verkauf prüfen“ und „Meiden“ gefallen.
                Daneben die Entwicklung des {data.benchmark} im selben Zeitraum. Aussagekräftig erst nach einigen Monaten.
              </p>
            </>
          );
        }}
      </Loaded>
    </section>
  );
}

export function AnalystSection() {
  const analyst = useAnalyst();
  return (
    <section className="panel" aria-labelledby="h-analyst">
      <div className="panel-head">
        <h2 id="h-analyst">Wöchentliche Einschätzungen</h2>
        {analyst.data?.run_date && <span className="meta">Stand {dayShort(analyst.data.run_date)}</span>}
      </div>
      <Loaded queries={[analyst]}>
        {() => {
          const items = analyst.data!.items;
          if (!items.length) {
            return <p className="empty-line">Der Analyst schätzt jeden Sonntag um 18 Uhr deine Depotpositionen und Watchlist-Werte ein. Die erste Einschätzung erscheint nach dem nächsten Lauf.</p>;
          }
          return (
            <>
              <Group title="Im Depot" items={items.filter((i) => i.kind === 'position')} />
              <Group title="Watchlist" items={items.filter((i) => i.kind === 'watchlist')} />
              <TrackRecordPanel />
              <p className="hint disclaimer">
                Automatisch erzeugt nach dem Ansatz „Trend + Rücksetzer“ aus Kursdaten und Nachrichten der Woche ({analyst.data!.model}).
                Keine Anlageberatung und keine Vorhersage: Prüfe jede Entscheidung selbst.
              </p>
            </>
          );
        }}
      </Loaded>
    </section>
  );
}
