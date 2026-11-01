// Verträge. Frage der Seite: Was kostet mich das, und was muss ich bald kündigen?
// Oben die Kosten aller laufenden Verträge als Leitfläche, daneben die Fristen der nächsten Wochen,
// darunter aus Kontoumsätzen erkannte Verträge und alle Verträge nach Art. Ein Klick auf einen Vertrag
// öffnet ihn zum Bearbeiten und Kündigen.
import { useState } from 'react';
import { type Contract, type ContractSuggestion, useContractSuggestions, useContracts } from '../../api/contracts';
import { CountUp } from '../../components/CountUp';
import { Icon } from '../../components/Icon';
import { Loaded } from '../../components/Loaded';
import { dayShort } from '../../lib/format';
import { useMoney } from '../../lib/privacy';
import { CancelContractDialog, ContractDialog, DeleteContractDialog } from './dialogs';
import { SOON_DAYS, STATUS_PILL, byCategory, dateLong, deadlineText, hasDeadline, inDays, intervalLabel, readDismissed, saveDismissed, soonCancellable } from './model';

type Open =
  | { type: 'add'; suggestion?: ContractSuggestion }
  | { type: 'edit'; contract: Contract }
  | { type: 'cancel'; contract: Contract }
  | { type: 'delete'; contract: Contract }
  | null;

export function ContractsPage() {
  const { eur } = useMoney();
  const contracts = useContracts();
  const [open, setOpen] = useState<Open>(null);
  const list = contracts.data?.contracts ?? [];
  const running = list.filter((c) => c.status !== 'ended');
  const soon = soonCancellable(list);
  const next = list.find(hasDeadline);
  const suggestions = useContractSuggestions();
  // Ausgeblendete Vorschläge merkt sich nur dieser Browser
  const [dismissed, setDismissed] = useState(readDismissed);
  const found = (suggestions.data ?? []).filter((s) => !dismissed.includes(s.key));
  const dismiss = (key: string) => {
    const keys = [...dismissed, key];
    setDismissed(keys);
    saveDismissed(keys);
  };

  return (
    <>
      <div className="title-row">
        <div className="text">
          <h1>Verträge</h1>
          <p className="sub">
            {next
              ? <>Nächste Frist: {next.name} bis {dateLong(next.cancel_by!)} kündbar{next.days_to_cancel! <= SOON_DAYS && <span className="signal"> ({inDays(next.days_to_cancel!)})</span>}</>
              : contracts.isSuccess && (list.length ? 'Gerade läuft keine Kündigungsfrist' : 'Versicherungen, Strom, Handy und Abos an einem Ort')}
          </p>
        </div>
        <div className="actions">
          <button className="btn btn-primary" onClick={() => setOpen({ type: 'add' })}><Icon name="plus" size={16} />Vertrag</button>
        </div>
      </div>

      <div className="grid grid-3">
        <section className="panel hero span-2" aria-labelledby="h-costs">
          <h2 className="lead-label" id="h-costs">Verträge kosten im Monat</h2>
          <Loaded queries={[contracts]} shape="figure">
            {() => (
              <>
                <div className="lead-figure"><CountUp value={contracts.data!.monthly_total} format={eur} /></div>
                <p className="lead-sub num">
                  {eur(contracts.data!.yearly_total)} im Jahr · {running.length === 1 ? '1 laufender Vertrag' : `${running.length} laufende Verträge`}
                </p>
              </>
            )}
          </Loaded>
        </section>

        <section className="panel" aria-labelledby="h-soon">
          <div className="panel-head">
            <h2 id="h-soon">Bald kündbar</h2>
            {soon.length > 0 && <span className="pill pill-signal">{soon.length}</span>}
          </div>
          <Loaded queries={[contracts]}>
            {() => soon.length === 0
              ? <p className="empty-line">In den nächsten {SOON_DAYS} Tagen endet keine Kündigungsfrist.</p>
              : (
                <div className="rows">
                  {soon.map((c) => (
                    <button className="row row-btn" key={c.id} onClick={() => setOpen({ type: 'edit', contract: c })}>
                      <span className="signal-dot" aria-hidden="true" />
                      <div className="grow">
                        <span className="trunc">{c.name}</span>
                        <span className="sub-line">bis {dateLong(c.cancel_by!)} zum {dateLong(c.cancel_effective!)}</span>
                      </div>
                      <span className="end strong">{inDays(c.days_to_cancel!)}</span>
                    </button>
                  ))}
                </div>
              )}
          </Loaded>
        </section>
      </div>

      {found.length > 0 && (
        <section className="panel" aria-labelledby="h-found">
          <div className="panel-head">
            <h2 id="h-found">Erkannt in deinen Umsätzen</h2>
            <span className="meta">regelmäßige Abbuchungen</span>
          </div>
          <div className="rows">
            {found.map((s) => (
              <div className="row" key={s.key}>
                <div className="grow">
                  <span className="trunc">{s.name}</span>
                  <span className="sub-line">{eur(s.amount)} {intervalLabel(s.interval)} · {s.count}× seit {dayShort(s.first_date)} · {s.category_name}</span>
                </div>
                <button className="btn btn-sm btn-primary" onClick={() => setOpen({ type: 'add', suggestion: s })}
                  aria-label={`${s.name} als Vertrag anlegen`}>Als Vertrag</button>
                <button className="icon-btn" onClick={() => dismiss(s.key)} aria-label={`${s.name} ausblenden`} title="Ausblenden">
                  <Icon name="close" size={16} />
                </button>
              </div>
            ))}
          </div>
        </section>
      )}

      <section className="panel" aria-labelledby="h-all">
        <div className="panel-head">
          <h2 id="h-all">Alle Verträge</h2>
          {contracts.data && list.length > 0 && <span className="meta">{list.length}</span>}
        </div>
        <Loaded queries={[contracts]}>
          {() => list.length === 0
            ? <p className="empty-line">Noch keine Verträge. Mit „Vertrag“ trägst du deinen ersten ein, FinTrack rechnet die Kündigungsfrist aus.</p>
            : byCategory(list).map((group) => (
              <div className="contract-group" key={group.category}>
                <h3 className="group-head">{group.label}</h3>
                <div className="rows">
                  {group.contracts.map((c) => (
                    <button className={`row row-btn${c.status === 'ended' ? ' is-paused' : ''}`} key={c.id}
                      onClick={() => setOpen({ type: 'edit', contract: c })}>
                      <div className="grow">
                        <span className="trunc">
                          {c.name}
                          {STATUS_PILL[c.status] && <span className="pill pill-inline">{STATUS_PILL[c.status]}</span>}
                        </span>
                        <span className="sub-line">{[c.provider, deadlineText(c)].filter(Boolean).join(' · ')}</span>
                      </div>
                      <div className="end">
                        <span className="strong">{eur(c.amount)}</span>
                        <span className="sub-line">{intervalLabel(c.interval)}</span>
                      </div>
                    </button>
                  ))}
                </div>
              </div>
            ))}
        </Loaded>
      </section>

      {open?.type === 'add' && (
        <ContractDialog onClose={() => setOpen(null)} prefill={open.suggestion && {
          name: open.suggestion.name, category: open.suggestion.kind, amount: open.suggestion.amount,
          interval: open.suggestion.interval, start_date: open.suggestion.first_date,
        }} />
      )}
      {open?.type === 'edit' && (
        <ContractDialog contract={open.contract} onClose={() => setOpen(null)}
          onCancelContract={(contract) => setOpen({ type: 'cancel', contract })}
          onDelete={(contract) => setOpen({ type: 'delete', contract })} />
      )}
      {open?.type === 'cancel' && <CancelContractDialog contract={open.contract} onClose={() => setOpen(null)} />}
      {open?.type === 'delete' && <DeleteContractDialog contract={open.contract} onClose={() => setOpen(null)} />}
    </>
  );
}
