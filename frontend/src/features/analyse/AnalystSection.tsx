// Wöchentliche Einschätzungen des Analysten auf der Analyse-Seite: pro Depotposition und
// Watchlist-Wert eine Stufe mit Begründung, Zuversicht und der Marke, ab der sie nicht mehr gilt.
// Geändert gegenüber der Vorwoche wird markiert. Automatisch erzeugt, keine Anlageberatung.
import { type AnalystItem, useAnalyst } from '../../api/analyst';
import { Loaded } from '../../components/Loaded';
import { dayShort } from '../../lib/format';
import { useMoney } from '../../lib/privacy';

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
