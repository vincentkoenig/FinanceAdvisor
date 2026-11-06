// Kontostände eintragen: Der neueste trägt den Cash-Bestand, ältere zeigen, wie gut die Buchungen
// dazwischen zum echten Konto passen.
import { useState, type FormEvent } from 'react';
import { type Balance, useBalances, useDeleteBalance, useSaveBalance } from '../../api/balances';
import { Dialog } from '../../components/Dialog';
import { Actions, type Errors, Field, apiErrors, describe } from '../../components/form';
import { Icon } from '../../components/Icon';
import { Loaded } from '../../components/Loaded';
import { useToast } from '../../components/Toast';
import { isoDay, parseAmount, parseDay } from '../../lib/format';
import { useMoney } from '../../lib/privacy';

const dayLong = (iso: string) => parseDay(iso).toLocaleDateString('de-DE', { day: '2-digit', month: '2-digit', year: 'numeric' });

export function BalancesDialog({ onClose }: { onClose: () => void }) {
  const { eur } = useMoney();
  const balances = useBalances();
  const save = useSaveBalance();
  const remove = useDeleteBalance();
  const notify = useToast();
  const today = isoDay(new Date());
  const [date, setDate] = useState(today);
  const [amount, setAmount] = useState('');
  const [errors, setErrors] = useState<Errors>({});

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    const found: Errors = {};
    const value = parseAmount(amount);
    if (value === null || Number.isNaN(value)) found.amount = 'Bitte den Kontostand eingeben, im Minus mit Vorzeichen.';
    if (!date) found.date = 'Bitte ein Datum wählen.';
    else if (date > today) found.date = 'Das Datum darf nicht in der Zukunft liegen.';
    setErrors(found);
    if (Object.keys(found).length) return;
    try {
      await save.mutateAsync({ date, amount: value! });
      notify('Kontostand gespeichert');
      setAmount('');
    } catch (error) {
      setErrors(apiErrors(error, { date: 'date', amount: 'amount' }));
    }
  };

  const drop = (balance: Balance) => remove.mutate(balance.id, {
    onSuccess: () => notify('Kontostand gelöscht'),
    onError: (error) => notify(error.message, { error: true }),
  });

  return (
    <Dialog title="Kontostände" onClose={onClose} busy={save.isPending}>
      <form onSubmit={submit} noValidate>
        <div className="form-grid">
          <Field id="balance-date" label="Datum" error={errors.date} hint="Stand am Ende dieses Tages">
            <input className="input" id="balance-date" type="date" max={today} value={date} onChange={(e) => setDate(e.target.value)} {...describe('balance-date', errors.date, true)} />
          </Field>
          <Field id="balance-amount" label="Kontostand in €" error={errors.amount} hint="Im Minus mit Vorzeichen, z. B. -250,50">
            <input className="input num" id="balance-amount" autoComplete="off" value={amount} onChange={(e) => setAmount(e.target.value)} {...describe('balance-amount', errors.amount, true)} />
          </Field>
        </div>
        <Actions onCancel={onClose} busy={save.isPending} label="Speichern" busyLabel="Speichert …" error={errors.form} />
      </form>

      <div className="balance-list">
        <Loaded queries={[balances]}>
          {() => balances.data!.length === 0
            ? <p className="empty-line">Noch kein Kontostand. Trage einen ein, dann rechnet FinTrack von dort mit deinen Buchungen weiter.</p>
            : (
              <div className="rows">
                {balances.data!.map((b) => (
                  <div className="row" key={b.id}>
                    <div className="grow">
                      <span className="trunc">{dayLong(b.date)}</span>
                      {b.difference !== null && Math.abs(b.difference) >= 1 && (
                        <span className="sub-line">{eur(b.difference, { sign: true })} gegenüber den Buchungen (erwartet: {eur(b.expected!)})</span>
                      )}
                      {b.difference !== null && Math.abs(b.difference) < 1 && <span className="sub-line">passt zu den Buchungen</span>}
                    </div>
                    <span className={`end strong${b.amount < 0 ? ' neg' : ''}`}>{eur(b.amount)}</span>
                    <button type="button" className="icon-btn" onClick={() => drop(b)} disabled={remove.isPending}
                      aria-label={`Kontostand vom ${dayLong(b.date)} löschen`} title="Löschen"><Icon name="trash" size={16} /></button>
                  </div>
                ))}
              </div>
            )}
        </Loaded>
      </div>
    </Dialog>
  );
}
