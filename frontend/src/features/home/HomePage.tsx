// Übersicht. Frage der Seite: Wie viel habe ich, und was ist heute zu tun?
// Oben das Gesamtvermögen als grüne Leitfläche und daneben das Fällige, darunter Monatsfluss,
// Tages-Update, größte Positionen und letzte Buchungen (auf dem Handy eingeklappt).
import type { UseQueryResult } from '@tanstack/react-query';
import type { ReactNode } from 'react';
import {
  type Booking, useBookings, useBudgetSummary, useExecutePlan, useInsight, usePortfolioHistory, usePositions, useSavingsPlans, useTrades,
} from '../../api/overview';
import { AreaLink } from '../../components/AreaLink';
import { Fold } from '../../components/Fold';
import { useToast } from '../../components/Toast';
import { dayShort, eur, monthName, parseDay, pct, tone } from '../../lib/format';
import {
  dayChange, largestPositions, monthFlow, planDates, portfolioTotals, recentBookings, signedAmount, token,
} from './model';

const quantityFormat = new Intl.NumberFormat('de-DE', { maximumFractionDigits: 6 });

// Lädt noch, Fehler mit "Erneut versuchen", oder der Inhalt
function Loaded({ queries, children }: { queries: UseQueryResult[]; children: () => ReactNode }) {
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

export function HomePage() {
  const positions = usePositions();
  const summary = useBudgetSummary();
  const history = usePortfolioHistory();
  const trades = useTrades();
  const plans = useSavingsPlans();
  const bookings = useBookings();
  const insight = useInsight();
  const execute = useExecutePlan();
  const notify = useToast();
  const today = new Date();
  const month = monthName(today);

  const totals = positions.data ? portfolioTotals(positions.data) : null;
  const change = history.data && trades.data && totals ? dayChange(history.data, totals.value, trades.data, today) : null;
  const dates = plans.data ? planDates(plans.data, today) : null;
  const flow = summary.data && plans.data ? monthFlow(summary.data, plans.data, today) : null;

  const runPlan = (id: number) => execute.mutate(id, {
    onSuccess: (result) => notify(`Sparplan ausgeführt: ${quantityFormat.format(result.quantity)} Stück zu ${eur(result.price)}`),
    onError: (error) => notify(error.message, { error: true }),
  });

  // Die wichtigste Nachricht des Tages unter dem Titel
  const firstDue = dates?.due[0];
  const finding = (
    <>
      {firstDue && <><span className="signal">Sparplan {firstDue.plan.asset_name} seit {dayShort(firstDue.date)} fällig</span> · </>}
      {change && <span className="nowrap">Depot seit gestern <span className={tone(change.abs)}>{eur(change.abs, { sign: true })}</span></span>}
      {change && flow && !firstDue && ' · '}
      {flow && !firstDue && <span className="nowrap">im {month} {eur(flow.left)} übrig</span>}
    </>
  );

  return (
    <>
      <div className="title-row">
        <div className="text">
          <h1>Übersicht</h1>
          <p className="sub">{finding}</p>
        </div>
      </div>

      <div className="grid grid-3">
        <section className="panel hero span-2" aria-labelledby="h-net">
          <h2 className="lead-label" id="h-net">Gesamtvermögen</h2>
          <Loaded queries={[positions, summary]}>
            {() => {
              const depot = totals!.value;
              const cash = summary.data!.cumulative_balance;
              const total = depot + cash;
              const showShare = depot > 0 && cash > 0;
              return (
                <>
                  <div className="lead-figure">{eur(total)}</div>
                  {showShare && (
                    <div className="share-bar" role="img"
                      aria-label={`Depot ${Math.round((depot / total) * 100)} %, Cash ${Math.round((cash / total) * 100)} %`}>
                      <span style={{ width: `${(depot / total) * 100}%`, background: 'var(--accent)' }} />
                      <span style={{ flex: 1, background: 'var(--hero-track)' }} />
                    </div>
                  )}
                  <p className="lead-sub num">
                    <span className="dot" style={{ background: 'var(--accent)' }} />Depot <b>{eur(depot)}</b>
                    <span className="dot dot-gap" style={{ background: 'var(--hero-track)' }} />Cash <b>{eur(cash)}</b>
                  </p>
                  <div className="strip">
                    <div>
                      <div className="kpi-label">Depot seit gestern</div>
                      {change
                        ? <><div className={`kpi-value ${tone(change.abs)}`}>{eur(change.abs, { sign: true })}</div>
                          <div className="kpi-sub">{change.pct === null ? 'kein Vortageswert' : pct(change.pct)}</div></>
                        : <><div className="kpi-value muted">–</div><div className="kpi-sub">{history.isPending || trades.isPending ? 'lädt …' : 'noch kein Verlauf'}</div></>}
                    </div>
                    <div>
                      <div className="kpi-label">Gewinn seit Kauf</div>
                      <div className="kpi-value">{eur(totals!.gain, { sign: true })}</div>
                      <div className="kpi-sub">
                        {totals!.gainPct === null ? 'noch keine Käufe' : `${pct(totals!.gainPct)} auf ${eur(totals!.cost, { digits: 0 })} Einstand`}
                      </div>
                    </div>
                    <div className="full">
                      <div className="kpi-label">Übrig im {month}</div>
                      <div className={`kpi-value${summary.data!.current_month_balance < 0 ? ' neg' : ''}`}>{eur(summary.data!.current_month_balance)}</div>
                      <div className="kpi-sub">von {eur(summary.data!.current_month_income)} Einnahmen</div>
                    </div>
                  </div>
                </>
              );
            }}
          </Loaded>
        </section>

        <section className="panel" aria-labelledby="h-todo">
          <div className="panel-head">
            <h2 id="h-todo">Zu tun</h2>
            {dates && dates.due.length > 0 && <span className="pill pill-signal">{dates.due.length} fällig</span>}
          </div>
          <Loaded queries={[plans]}>
            {() => dates!.due.length + dates!.upcoming.length === 0
              ? <p className="empty-line">Nichts zu tun. Sparpläne legst du im <AreaLink area="portfolio" className="link">Portfolio</AreaLink> an.</p>
              : (
                <div className="rows">
                  {dates!.due.map(({ plan, date }) => (
                    <div className="row" key={plan.id}>
                      <span className="signal-dot" aria-hidden="true" />
                      <div className="grow">
                        <span className="trunc">Sparplan {plan.asset_name}</span>
                        <span className="sub-line">{eur(plan.amount)} · fällig seit {dayShort(date)}</span>
                      </div>
                      <button className="btn btn-primary btn-sm" onClick={() => runPlan(plan.id)}
                        disabled={execute.isPending} aria-label={`Sparplan ${plan.asset_name} ausführen`}>
                        {execute.isPending && execute.variables === plan.id ? 'Läuft …' : 'Ausführen'}
                      </button>
                    </div>
                  ))}
                  {dates!.upcoming.map(({ plan, date }) => (
                    <div className="row" key={plan.id}>
                      <div className="grow">
                        <span className="trunc">Sparplan {plan.asset_name}</span>
                        <span className="sub-line">{eur(plan.amount)} · am {dayShort(date)}</span>
                      </div>
                      <span className="pill">geplant</span>
                    </div>
                  ))}
                </div>
              )}
          </Loaded>
        </section>
      </div>

      <div className="grid grid-3">
        <Fold id="h-flow" className="span-2" title={`${month[0].toUpperCase()}${month.slice(1)} im Haushaltsbuch`}
          peek={flow ? eur(flow.left) : ''}
          action={<AreaLink area="budget" className="btn btn-text btn-sm">Öffnen</AreaLink>}>
          <Loaded queries={[summary, plans]}>
            {() => <MonthFlow flow={flow!} />}
          </Loaded>
        </Fold>

        <Fold id="h-insight" title="Tages-Update"
          peek={insight.data?.content ? 'neu' : ''}
          action={insight.data?.created_at && <span className="meta">KI · {dayShort(insight.data.created_at)}</span>}>
          <Loaded queries={[insight]}>
            {() => insight.data!.content
              ? <p className="insight">{insight.data!.content}</p>
              : <p className="empty-line">Das Tages-Update erscheint jeden Morgen, sobald es Daten zu deinem Depot oder Haushaltsbuch gibt.</p>}
          </Loaded>
        </Fold>
      </div>

      <div className="grid grid-2">
        <Fold id="h-positions" title="Größte Positionen"
          peek={positions.data?.length ? `${positions.data.length} im Depot` : ''}
          action={positions.data?.length ? <AreaLink area="portfolio" className="btn btn-text btn-sm">Alle {positions.data.length}</AreaLink> : null}>
          <Loaded queries={[positions]}>
            {() => positions.data!.length === 0
              ? <p className="empty-line">Noch keine Positionen. Im <AreaLink area="portfolio" className="link">Portfolio</AreaLink> legst du die erste an.</p>
              : (
                <div className="rows">
                  {largestPositions(positions.data!).map((p) => (
                    <div className="row" key={p.asset_id}>
                      <span className="token" aria-hidden="true">{token(p.symbol, p.name)}</span>
                      <div className="grow">
                        <span className="trunc">{p.name}</span>
                        <span className="sub-line">{eur(p.value)}</span>
                      </div>
                      <div className="end">
                        <span className={tone(p.gain)}>{p.gainPct === null ? '–' : pct(p.gainPct)}</span>
                        <span className="sub-line">{eur(p.gain, { sign: true })} seit Kauf</span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
          </Loaded>
        </Fold>

        <Fold id="h-bookings" title="Letzte Buchungen"
          peek={bookings.data?.length ? bookingAmount(recentBookings(bookings.data, 1)[0]) : ''}
          action={bookings.data?.length ? <AreaLink area="budget" className="btn btn-text btn-sm">Alle {bookings.data.length}</AreaLink> : null}>
          <Loaded queries={[bookings]}>
            {() => bookings.data!.length === 0
              ? <p className="empty-line">Noch keine Buchungen. Im <AreaLink area="budget" className="link">Haushaltsbuch</AreaLink> trägst du Einnahmen und Ausgaben ein.</p>
              : (
                <div className="rows">
                  {recentBookings(bookings.data!).map((b) => (
                    <div className="row" key={b.id}>
                      <div className="grow">
                        <span className="trunc">{b.description || b.category_name || 'Buchung'}</span>
                        <span className="sub-line">
                          {[b.category_name, `${b.is_recurring ? 'monatlich ab ' : ''}${dayShort(parseDay(b.date))}`, b.is_paused ? 'pausiert' : null]
                            .filter(Boolean).join(' · ')}
                        </span>
                      </div>
                      <div className={`end${signedAmount(b) > 0 ? ' pos' : ''}`}>{bookingAmount(b)}</div>
                    </div>
                  ))}
                </div>
              )}
          </Loaded>
        </Fold>
      </div>
    </>
  );
}

function bookingAmount(b: Booking) {
  return eur(signedAmount(b), { sign: signedAmount(b) > 0 });
}

// Signatur der Seite: wohin das Einkommen des Monats geht
function MonthFlow({ flow }: { flow: ReturnType<typeof monthFlow> }) {
  if (flow.income <= 0 && flow.parts.every((p) => p.value === 0)) {
    return <p className="empty-line">Für diesen Monat gibt es noch keine Buchungen.</p>;
  }
  const share = (value: number) => (flow.income > 0 ? Math.round((value / flow.income) * 100) : 0);
  return (
    <>
      <p className="muted num">Einnahmen <b className="strong">{eur(flow.income)}</b></p>
      {flow.drawable
        ? (
          <div className="flow" role="img" aria-label={flow.parts.map((p) => `${p.label} ${share(p.value)} %`).join(', ')}>
            {flow.parts.filter((p) => p.value > 0).map((p) => (
              <span key={p.key} className={`flow-${p.key}`} style={{ flex: p.value }}>
                {p.value / flow.income > 0.12 ? p.short : ''}
              </span>
            ))}
          </div>
        )
        : <p className="flow-note neg">Die Ausgaben liegen {eur(-flow.left)} über den Einnahmen.</p>}
      <table className="legend-table num">
        <tbody>
          {flow.parts.map((p) => (
            <tr key={p.key}>
              <td><span className={`dot flow-${p.key}`} />{p.label}</td>
              <td className="r">{eur(p.value)}</td>
              <td className="r muted pct-col">{flow.income > 0 ? `${share(p.value)} %` : ''}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  );
}
