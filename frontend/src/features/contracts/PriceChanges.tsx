// Preisänderungen, die FinTrack an den Abbuchungen erkannt hat: "Netflix kostet jetzt 13,99 € statt 12,99 €".
// Übernehmen ändert den Vertrag bzw. führt die wiederkehrende Buchung ab dem neuen Preis weiter,
// Ignorieren blendet den Hinweis aus (bis sich der Preis noch einmal ändert).
// Auf der Vertragsseite stehen alle, im Haushaltsbuch nur die wiederkehrenden Buchungen.
import { type PriceChange, useAcceptPriceChange, useDismissPriceChange, usePriceChanges } from '../../api/contracts';
import { useToast } from '../../components/Toast';
import { dayShort } from '../../lib/format';
import { useMoney } from '../../lib/privacy';
import { intervalLabel } from './model';

export function PriceChanges({ only }: { only?: PriceChange['kind'] }) {
  const { eur } = useMoney();
  const changes = usePriceChanges();
  const accept = useAcceptPriceChange();
  const dismiss = useDismissPriceChange();
  const notify = useToast();
  const list = (changes.data ?? []).filter((c) => !only || c.kind === only);
  if (!list.length) return null;
  const busy = accept.isPending || dismiss.isPending;

  const run = (action: typeof accept, change: PriceChange) => action.mutate(change.key, {
    onSuccess: (result) => notify(result.message),
    onError: (error) => notify(error.message, { error: true }),
  });

  return (
    <section className="panel price-changes" aria-labelledby="h-prices">
      <div className="panel-head">
        <h2 id="h-prices">Neue Preise erkannt</h2>
        <span className="meta">aus deinen Abbuchungen</span>
      </div>
      <div className="rows">
        {list.map((change) => {
          const up = change.new_amount > change.old_amount;
          return (
            <div className="row" key={change.key}>
              <div className="grow">
                <span className="trunc">
                  {change.name} kostet jetzt <span className="strong">{eur(change.new_amount)}</span> statt {eur(change.old_amount)}
                </span>
                <span className="sub-line">
                  {intervalLabel(change.interval)} · seit {dayShort(change.since)} ·{' '}
                  <span className={up ? 'neg' : 'pos'}>{eur(change.yearly_difference, { sign: true })} im Jahr</span>
                </span>
              </div>
              <button className="btn btn-sm btn-primary" onClick={() => run(accept, change)} disabled={busy}
                aria-label={`Neuen Preis für ${change.name} übernehmen`}>Übernehmen</button>
              <button className="btn btn-sm" onClick={() => run(dismiss, change)} disabled={busy}
                aria-label={`Hinweis zu ${change.name} ignorieren`}>Ignorieren</button>
            </div>
          );
        })}
      </div>
    </section>
  );
}
