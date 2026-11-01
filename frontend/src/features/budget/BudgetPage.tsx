// Haushaltsbuch. Frage der Seite: Wie viel bleibt diesen Monat übrig?
// Oben "Übrig im Monat" als Leitfläche mit dem Monatsfluss, daneben die Ausgaben nach Kategorie,
// darunter alle Buchungen des Monats. Mit den Pfeilen geht es in andere Monate.
import { useState } from 'react';
import { Link } from 'react-router';
import { type Category, useCategories, useMonthBookings, useTogglePause } from '../../api/budget';
import { type Booking, useBudgetSummary, useSavingsPlans } from '../../api/overview';
import { CountUp } from '../../components/CountUp';
import { Icon } from '../../components/Icon';
import { Loaded } from '../../components/Loaded';
import { MonthFlow } from '../../components/MonthFlow';
import { useToast } from '../../components/Toast';
import { dayShort, isoDay, monthKey, parseDay } from '../../lib/format';
import { useMoney } from '../../lib/privacy';
import { monthFlow, signedAmount } from '../home/model';
import { AddBookingDialog, DeleteBookingDialog } from './dialogs';
import {
  asSummary, counts, dayInMonth, daysForAverage, expensesByCategory, largestVariable, mainCategory, monthStart, monthTotals, sortBookings,
} from './model';

const monthLabel = (month: Date) => month.toLocaleDateString('de-DE', { month: 'long', year: 'numeric' });
const monthOnly = (month: Date) => month.toLocaleDateString('de-DE', { month: 'long' });
const dayMonth = (iso: string) => parseDay(iso).toLocaleDateString('de-DE', { day: '2-digit', month: '2-digit' });

type Open = { type: 'add' } | { type: 'delete'; booking: Booking } | null;

export function BudgetPage() {
  const { eur } = useMoney();
  const today = new Date();
  const [offset, setOffset] = useState(0);
  const month = monthStart(today, offset);
  const key = monthKey(month);
  const current = offset === 0;
  const bookings = useMonthBookings(key);
  const categories = useCategories();
  const summary = useBudgetSummary();
  const plans = useSavingsPlans();
  const [open, setOpen] = useState<Open>(null);

  const totals = bookings.data ? monthTotals(bookings.data, month) : null;
  const top = bookings.data ? largestVariable(bookings.data, month) : null;
  // Neue Buchungen im laufenden Monat auf heute, sonst auf den Ersten des gezeigten Monats
  const defaultDate = current ? isoDay(today) : isoDay(month);

  const switcher = (
    <div className="month-switch" role="group" aria-label="Monat">
      <button className="icon-btn" onClick={() => setOffset((o) => o - 1)} aria-label="Vorheriger Monat"><Icon name="left" size={16} /></button>
      <span aria-live="polite">{monthLabel(month)}</span>
      <button className="icon-btn" onClick={() => setOffset((o) => o + 1)} aria-label="Nächster Monat"><Icon name="right" size={16} /></button>
    </div>
  );

  return (
    <>
      <div className="title-row">
        <div className="text">
          <h1>Haushaltsbuch</h1>
          <p className="sub">
            {top
              ? <>Größte variable Ausgabe im {monthOnly(month)}: {top.description || top.category_name} mit {eur(top.amount)}</>
              : bookings.isSuccess && <>Im {monthOnly(month)} noch keine variablen Ausgaben</>}
          </p>
        </div>
        <div className="actions">
          {switcher}
          <Link to="/budget/import" className="btn"><Icon name="upload" size={16} />Importieren</Link>
          <button className="btn btn-primary" onClick={() => setOpen({ type: 'add' })}><Icon name="plus" size={16} />Buchung</button>
        </div>
      </div>

      <div className="grid grid-3">
        <section className="panel hero span-2" aria-labelledby="h-left">
          <h2 className="lead-label" id="h-left">Übrig im {monthOnly(month)}</h2>
          <Loaded queries={[bookings]} shape="figure">
            {() => (
              <>
                <div className={`lead-figure${totals!.left < 0 ? ' neg' : ''}`}><CountUp value={totals!.left} format={eur} /></div>
                <p className="lead-sub num">
                  {totals!.income > 0 && <>{Math.round((totals!.left / totals!.income) * 100)} % der Einnahmen · </>}
                  {summary.data ? <>Cash-Bestand insgesamt {eur(summary.data.cumulative_balance)}</> : 'Cash-Bestand lädt …'}
                </p>
                <div className="hero-flow">
                  {/* Sparpläne kennen nur ihre letzte Ausführung, darum zählen sie nur im laufenden Monat */}
                  <MonthFlow flow={monthFlow(asSummary(totals!, 0), current ? plans.data ?? [] : [], month)} />
                </div>
              </>
            )}
          </Loaded>
        </section>

        <section className="panel" aria-labelledby="h-cat">
          <div className="panel-head"><h2 id="h-cat">Ausgaben nach Kategorie</h2></div>
          <Loaded queries={[bookings, categories]}>
            {() => {
              const rows = expensesByCategory(bookings.data!, categories.data!, month);
              if (rows.length === 0) return <p className="empty-line">Keine Ausgaben im {monthOnly(month)}.</p>;
              const spent = totals!.fixed + totals!.variable;
              const max = rows[0].value;
              return (
                <>
                  <ol className="bar-list num">
                    {rows.map((r, i) => (
                      <li key={r.label}>
                        <span className="trunc">{r.label}</span>
                        <span className="strong">{eur(r.value)}</span>
                        <span className="bar" style={{ width: `${(r.value / max) * 100}%`, background: i === 0 ? 'var(--accent)' : 'var(--chart-muted)' }} />
                      </li>
                    ))}
                  </ol>
                  <div className="row total-row"><span className="grow">Ausgaben gesamt</span><span className="end strong">{eur(spent)}</span></div>
                  <div className="row"><span className="grow muted">Im Schnitt pro Tag</span><span className="end">{eur(spent / daysForAverage(month, today))}</span></div>
                </>
              );
            }}
          </Loaded>
        </section>
      </div>

      <section className="panel" aria-labelledby="h-bookings">
        <div className="panel-head">
          <h2 id="h-bookings">Buchungen</h2>
          {bookings.data && <span className="meta">{bookings.data.length} im {monthOnly(month)}</span>}
        </div>
        <Loaded queries={[bookings, categories]}>
          {() => bookings.data!.length === 0
            ? (
              <p className="empty-line">
                Keine Buchungen im {monthOnly(month)}. {current ? 'Mit „Buchung“ trägst du Einnahmen und Ausgaben ein.' : 'Wiederkehrende Buchungen erscheinen, sobald sie laufen.'}
              </p>
            )
            : <Bookings bookings={sortBookings(bookings.data!, month)} month={month} categories={categories.data!} onDelete={(booking) => setOpen({ type: 'delete', booking })} />}
        </Loaded>
      </section>

      {open?.type === 'add' && <AddBookingDialog defaultDate={defaultDate} onClose={() => setOpen(null)} />}
      {open?.type === 'delete' && <DeleteBookingDialog booking={open.booking} onClose={() => setOpen(null)} />}
    </>
  );
}

type BookingsProps = { bookings: Booking[]; month: Date; categories: Category[]; onDelete: (b: Booking) => void };

function Bookings({ bookings, month, categories, onDelete }: BookingsProps) {
  const { eur } = useMoney();
  const toggle = useTogglePause();
  const notify = useToast();
  const name = (b: Booking) => b.description || b.category_name || 'Buchung';
  const amount = (b: Booking) => eur(signedAmount(b), { sign: signedAmount(b) > 0 });
  const where = (b: Booking) => {
    const main = mainCategory(b.category_id, categories);
    return main && main.name !== b.category_name ? `${main.name} · ${b.category_name}` : b.category_name ?? '';
  };
  const pause = (b: Booking) => toggle.mutate(b.id, {
    onSuccess: (result) => notify(result.is_paused ? `${name(b)} pausiert, zählt ab diesem Monat nicht mehr` : `${name(b)} läuft wieder`),
    onError: (error) => notify(error.message, { error: true }),
  });
  // Aus Sicht des gezeigten Monats: pausiert erst später, dann zählt sie hier noch
  const paused = (b: Booking) => b.is_paused && !counts(b, month);
  const actions = (b: Booking) => (
    <>
      {b.is_recurring && (
        <button className="icon-btn" onClick={() => pause(b)} disabled={toggle.isPending}
          aria-label={`${name(b)} ${b.is_paused ? 'fortsetzen' : 'pausieren'}`} title={b.is_paused ? 'Fortsetzen' : 'Pausieren'}>
          <Icon name={b.is_paused ? 'play' : 'pause'} size={16} />
        </button>
      )}
      <button className="icon-btn" onClick={() => onDelete(b)} aria-label={`${name(b)} löschen`} title="Löschen"><Icon name="trash" size={16} /></button>
    </>
  );

  return (
    <>
      <div className="table-wrap desktop-only">
        <table className="table">
          <thead>
            <tr>
              <th className="r date-col">Datum</th><th>Buchung</th><th className="r">Betrag</th>
              <th className="r actions-col"><span className="sr-only">Aktionen</span></th>
            </tr>
          </thead>
          <tbody>
            {bookings.map((b) => (
              <tr key={b.id} className={paused(b) ? 'is-paused' : undefined}>
                <td className="r muted">{dayMonth(dayInMonth(b, month))}</td>
                <td>
                  <span className="trunc">
                    {name(b)}
                    {b.is_recurring && <span className="pill pill-inline">{paused(b) ? 'pausiert' : 'monatlich'}</span>}
                  </span>
                  <span className="sub-line">{where(b)}</span>
                </td>
                <td className={`r strong${signedAmount(b) > 0 ? ' pos' : ''}`}>{amount(b)}</td>
                <td className="r nowrap">{actions(b)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="rows only-phone">
        {bookings.map((b) => (
          <div className={`row${paused(b) ? ' is-paused' : ''}`} key={b.id}>
            <div className="grow">
              <span className="trunc">{name(b)}</span>
              <span className="sub-line">
                {[dayShort(dayInMonth(b, month)), mainCategory(b.category_id, categories)?.name ?? b.category_name, b.is_recurring ? (paused(b) ? 'pausiert' : 'monatlich') : null]
                  .filter(Boolean).join(' · ')}
              </span>
            </div>
            <span className={`end strong${signedAmount(b) > 0 ? ' pos' : ''}`}>{amount(b)}</span>
            {actions(b)}
          </div>
        ))}
      </div>
    </>
  );
}
