// Dialoge der Verträge: anlegen/bearbeiten, kündigen und löschen.
import { useState, type FormEvent } from 'react';
import { useCategories } from '../../api/budget';
import {
  type Contract, type ContractCategory, type ContractInput, type NoticeUnit, type PaymentInterval,
  useAddContract, useCancelContract, useContracts, useDeleteContract, useLinkBooking, useUndoCancel, useUnlinkBooking, useUpdateContract,
} from '../../api/contracts';
import { useBookings } from '../../api/overview';
import { Dialog } from '../../components/Dialog';
import { Actions, type Errors, Field, apiErrors, describe, positive } from '../../components/form';
import { useToast } from '../../components/Toast';
import { isoDay, parseAmount } from '../../lib/format';
import { useMoney } from '../../lib/privacy';
import { CATEGORIES, INTERVALS, NOTICE_UNITS, RENEWALS, TYPICAL_TERMS, bookingChoices, dateLong, deadlineText, monthlyShare, suggestCategory } from './model';

const FIELDS: Record<string, string> = {
  name: 'name', provider: 'provider', contract_number: 'number', amount: 'amount', start_date: 'start',
  min_term_months: 'minTerm', renewal_months: 'minTerm', notice_value: 'notice', notes: 'notes',
};

/** Ganze Zahl im Bereich, leer → null; sonst Meldung in errors */
function wholeNumber(text: string, min: number, max: number, errors: Errors, key: string, message: string) {
  if (text.trim() === '') return null;
  const value = Number(text);
  if (!Number.isInteger(value) || value < min || value > max) {
    errors[key] = message;
    return null;
  }
  return value;
}

type Props = {
  contract?: Contract;
  /** Vorbelegung für einen neuen Vertrag, z. B. aus einer erkannten Abbuchung */
  prefill?: Partial<ContractInput>;
  onClose: () => void;
  onCancelContract?: (contract: Contract) => void;
  onDelete?: (contract: Contract) => void;
};

export function ContractDialog({ contract, prefill, onClose, onCancelContract, onDelete }: Props) {
  const add = useAddContract();
  const update = useUpdateContract();
  const undo = useUndoCancel();
  const link = useLinkBooking();
  const unlink = useUnlinkBooking();
  const notify = useToast();
  const { eur } = useMoney();
  const categories = useCategories();
  const bookings = useBookings();
  const contracts = useContracts();
  // Neuester Stand des Vertrags, damit z. B. das Lösen der Verknüpfung sofort sichtbar ist
  const live = contracts.data?.contracts.find((c) => c.id === contract?.id) ?? contract;
  const choices = bookingChoices(categories.data ?? [], bookings.data ?? [], contracts.data?.contracts ?? []);
  const kind = prefill?.category ?? 'insurance';
  const start = contract ?? { category: kind, ...TYPICAL_TERMS[kind], ...prefill };
  const [name, setName] = useState(contract?.name ?? prefill?.name ?? '');
  const [category, setCategory] = useState<ContractCategory>(start.category);
  const [provider, setProvider] = useState(contract?.provider ?? '');
  const [number, setNumber] = useState(contract?.contract_number ?? '');
  const initialAmount = contract?.amount ?? prefill?.amount;
  const [amount, setAmount] = useState(initialAmount ? initialAmount.toFixed(2).replace('.', ',') : '');
  const [payInterval, setPayInterval] = useState<PaymentInterval>(start.interval);
  const [startDate, setStartDate] = useState(contract?.start_date ?? prefill?.start_date ?? isoDay(new Date()));
  const [minTerm, setMinTerm] = useState(start.min_term_months?.toString() ?? '');
  const [renewal, setRenewal] = useState<number | null>(start.renewal_months);
  const [notice, setNotice] = useState(String(start.notice_value));
  const [unit, setUnit] = useState<NoticeUnit>(start.notice_unit);
  const [notes, setNotes] = useState(contract?.notes ?? '');
  // Solange die Bedingungen nicht von Hand geändert wurden, folgen sie der gewählten Art
  // Erkannte Zahlweise soll ein Wechsel der Art nicht überschreiben
  const [termsTouched, setTermsTouched] = useState(Boolean(contract || prefill));
  // Haushaltsbuch: 'none', 'c<Kategorie-ID>' für eine neue Buchung oder 't<Buchungs-ID>' für eine vorhandene.
  // Ohne eigene Wahl schlägt ein neuer Vertrag eine neue Buchung in der passendsten Fixkosten-Kategorie vor.
  // Aus Umsätzen erkannte Verträge stehen schon im Haushaltsbuch: nicht noch einmal als Fixkosten eintragen
  const [linkChoice, setLinkChoice] = useState<string | null>(contract || prefill ? 'none' : null);
  const suggested = suggestCategory(choices.categories, name, category);
  const chosenLink = linkChoice ?? (suggested ? `c${suggested.id}` : 'none');
  const [errors, setErrors] = useState<Errors>({});
  const busy = add.isPending || update.isPending || undo.isPending || link.isPending || unlink.isPending;
  const share = monthlyShare(parseAmount(amount), payInterval);
  const bookingHint = chosenLink.startsWith('c') && share
    ? `Als Fixkosten mit ${eur(share)} pro Monat, ab diesem Monat`
    : choices.categories.length === 0 ? 'Für eine neue Buchung fehlt im Haushaltsbuch eine Fixkosten-Kategorie' : undefined;

  const chooseCategory = (next: ContractCategory) => {
    setCategory(next);
    if (termsTouched) return;
    const terms = TYPICAL_TERMS[next];
    setPayInterval(terms.interval);
    setMinTerm(terms.min_term_months?.toString() ?? '');
    setRenewal(terms.renewal_months);
    setNotice(String(terms.notice_value));
    setUnit(terms.notice_unit);
  };
  const touched = <T,>(set: (value: T) => void) => (value: T) => { setTermsTouched(true); set(value); };

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    const found: Errors = {};
    if (!name.trim()) found.name = 'Bitte einen Namen eingeben.';
    const value = positive(amount, 'einen Beitrag', found, 'amount');
    if (!startDate) found.start = 'Bitte den Vertragsbeginn wählen.';
    const minTermValue = wholeNumber(minTerm, 1, 120, found, 'minTerm', 'Bitte 1 bis 120 Monate oder leer lassen.');
    if (!found.minTerm && minTermValue === null && renewal === null) found.minTerm = 'Ohne Verlängerung braucht der Vertrag eine Laufzeit.';
    const noticeValue = wholeNumber(notice, 0, 365, found, 'notice', 'Bitte eine ganze Zahl von 0 bis 365.') ?? 0;
    setErrors(found);
    if (Object.keys(found).length) return;

    const body: ContractInput = {
      name: name.trim(), provider: provider.trim() || null, category, contract_number: number.trim() || null,
      amount: value, interval: payInterval, start_date: startDate, min_term_months: minTermValue, renewal_months: renewal,
      notice_value: noticeValue, notice_unit: unit, notes: notes.trim() || null,
    };
    let saved: Contract;
    try {
      saved = (contract ? await update.mutateAsync({ id: contract.id, body }) : await add.mutateAsync(body)).contract;
    } catch (error) {
      setErrors(apiErrors(error, FIELDS));
      return;
    }
    if (!saved.booking && chosenLink !== 'none') {
      const target = Number(chosenLink.slice(1));
      try {
        await link.mutateAsync(chosenLink.startsWith('c') ? { id: saved.id, category_id: target } : { id: saved.id, transaction_id: target });
        notify(`${body.name} gespeichert und im Haushaltsbuch eingetragen: ${deadlineText(saved)}`);
      } catch (error) {
        // Der Vertrag ist gespeichert, nur die Buchung fehlt: nicht noch einmal anlegen lassen
        notify(`${body.name} gespeichert, aber nicht im Haushaltsbuch eingetragen: ${(error as Error).message}`, { error: true });
      }
    } else {
      notify(`${body.name} gespeichert: ${deadlineText(saved)}`);
    }
    onClose();
  };

  const unlinkBooking = () => unlink.mutate(contract!.id, {
    onSuccess: () => notify(`Verknüpfung gelöst, die Buchung bleibt im Haushaltsbuch`),
    onError: (error) => setErrors({ form: error.message }),
  });

  const undoCancel = () => undo.mutate(contract!.id, {
    onSuccess: () => { notify(`Kündigung von ${contract!.name} zurückgenommen`); onClose(); },
    onError: (error) => setErrors({ form: error.message }),
  });

  return (
    <Dialog title={contract ? contract.name : 'Vertrag hinzufügen'} onClose={onClose} busy={busy}>
      <form className="dialog-form" onSubmit={submit} noValidate>
        <Field id="contract-name" label="Name" error={errors.name}>
          <input className="input" id="contract-name" placeholder="z. B. Haftpflicht" maxLength={80} value={name}
            onChange={(e) => setName(e.target.value)} {...describe('contract-name', errors.name)} />
        </Field>
        <div className="form-grid">
          <Field id="contract-category" label="Art">
            <select className="select" id="contract-category" value={category} onChange={(e) => chooseCategory(e.target.value as ContractCategory)}>
              {CATEGORIES.map((c) => <option key={c.value} value={c.value}>{c.label}</option>)}
            </select>
          </Field>
          <Field id="contract-provider" label="Anbieter" error={errors.provider}>
            <input className="input" id="contract-provider" placeholder="optional" maxLength={80} value={provider}
              onChange={(e) => setProvider(e.target.value)} {...describe('contract-provider', errors.provider)} />
          </Field>
          <Field id="contract-amount" label="Beitrag" error={errors.amount}>
            <input className="input" id="contract-amount" inputMode="decimal" placeholder="0,00 €" value={amount}
              onChange={(e) => setAmount(e.target.value)} {...describe('contract-amount', errors.amount)} />
          </Field>
          <Field id="contract-interval" label="Zahlweise">
            <select className="select" id="contract-interval" value={payInterval} onChange={(e) => touched(setPayInterval)(e.target.value as PaymentInterval)}>
              {INTERVALS.map((i) => <option key={i.value} value={i.value}>{i.label}</option>)}
            </select>
          </Field>
          <Field id="contract-start" label="Beginn" error={errors.start}>
            <input className="input" id="contract-start" type="date" value={startDate}
              onChange={(e) => setStartDate(e.target.value)} {...describe('contract-start', errors.start)} />
          </Field>
          <Field id="contract-number" label="Vertragsnummer" error={errors.number}>
            <input className="input" id="contract-number" placeholder="optional" maxLength={60} value={number}
              onChange={(e) => setNumber(e.target.value)} {...describe('contract-number', errors.number)} />
          </Field>
          <Field id="contract-min-term" label="Mindestlaufzeit in Monaten" error={errors.minTerm} hint="Leer, wenn es keine gibt">
            <input className="input" id="contract-min-term" inputMode="numeric" placeholder="keine" value={minTerm}
              onChange={(e) => touched(setMinTerm)(e.target.value)} {...describe('contract-min-term', errors.minTerm, true)} />
          </Field>
          <Field id="contract-renewal" label="Verlängert sich danach">
            <select className="select" id="contract-renewal" value={renewal ?? ''}
              onChange={(e) => touched(setRenewal)(e.target.value === '' ? null : Number(e.target.value))}>
              {RENEWALS.map((r) => <option key={r.label} value={r.value ?? ''}>{r.label}</option>)}
            </select>
          </Field>
          <Field id="contract-notice" label="Kündigungsfrist" error={errors.notice}>
            <input className="input" id="contract-notice" inputMode="numeric" value={notice}
              onChange={(e) => touched(setNotice)(e.target.value)} {...describe('contract-notice', errors.notice)} />
          </Field>
          <Field id="contract-notice-unit" label="Frist in">
            <select className="select" id="contract-notice-unit" value={unit} onChange={(e) => touched(setUnit)(e.target.value as NoticeUnit)}>
              {NOTICE_UNITS.map((u) => <option key={u.value} value={u.value}>{u.label}</option>)}
            </select>
          </Field>
          <div className="full">
            <Field id="contract-notes" label="Notiz" error={errors.notes}>
              <textarea className="input textarea" id="contract-notes" placeholder="optional, z. B. Teilkasko, 150 € SB" maxLength={1000} rows={2}
                value={notes} onChange={(e) => setNotes(e.target.value)} {...describe('contract-notes', errors.notes)} />
            </Field>
          </div>
        </div>
        {live?.booking
          ? (
            <div className="switch-row">
              <div className="text">
                <span className="strong">Im Haushaltsbuch</span>
                <p className="hint">{[live.booking.category_name, `${eur(live.booking.amount)} pro Monat`].filter(Boolean).join(' · ')}</p>
              </div>
              <button type="button" className="btn btn-sm" onClick={unlinkBooking} disabled={busy}>Verknüpfung lösen</button>
            </div>
          )
          : (
            <Field id="contract-booking" label="Im Haushaltsbuch" hint={bookingHint}>
              <select className="select" id="contract-booking" value={chosenLink} onChange={(e) => setLinkChoice(e.target.value)}
                {...describe('contract-booking', undefined, Boolean(bookingHint))}>
                <option value="none">Nicht eintragen</option>
                {choices.categories.length > 0 && (
                  <optgroup label="Neue Buchung in">
                    {choices.categories.map((c) => <option key={c.id} value={`c${c.id}`}>{c.label}</option>)}
                  </optgroup>
                )}
                {choices.bookings.length > 0 && (
                  <optgroup label="Vorhandene Buchung">
                    {choices.bookings.map((b) => <option key={b.id} value={`t${b.id}`}>{b.label} · {eur(b.amount)}</option>)}
                  </optgroup>
                )}
              </select>
            </Field>
          )}
        {contract && (
          <div className="dialog-extra">
            {live!.end_date
              ? <button type="button" className="btn btn-sm" onClick={undoCancel} disabled={busy}>Kündigung zurücknehmen</button>
              : <button type="button" className="btn btn-sm" onClick={() => onCancelContract?.(contract)} disabled={busy}>Als gekündigt markieren</button>}
            <button type="button" className="btn btn-sm btn-danger" onClick={() => onDelete?.(contract)} disabled={busy}>Löschen</button>
          </div>
        )}
        <Actions onCancel={onClose} busy={busy} label="Speichern" busyLabel="Speichert …" error={errors.form} />
      </form>
    </Dialog>
  );
}

export function CancelContractDialog({ contract, onClose }: { contract: Contract; onClose: () => void }) {
  const cancel = useCancelContract();
  const notify = useToast();
  const suggested = contract.cancel_effective ?? contract.ends_on ?? '';
  const [endDate, setEndDate] = useState(suggested);
  const [errors, setErrors] = useState<Errors>({});

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!endDate) {
      setErrors({ end: 'Bitte das Enddatum wählen.' });
      return;
    }
    try {
      await cancel.mutateAsync({ id: contract.id, end_date: endDate });
      notify(`${contract.name} gekündigt, endet am ${dateLong(endDate)}`);
      onClose();
    } catch (error) {
      setErrors(apiErrors(error, { end_date: 'end' }));
    }
  };

  return (
    <Dialog title={`${contract.name} kündigen`} onClose={onClose} busy={cancel.isPending}>
      <form className="dialog-form" onSubmit={submit} noValidate>
        <p className="muted">
          FinTrack schickt keine Kündigung ab. Trag hier ein, dass du gekündigt hast, dann zählt der Vertrag nach dem Ende nicht mehr mit.
        </p>
        <Field id="cancel-end" label="Endet am" error={errors.end}
          hint={contract.cancel_effective ? `Nächstmöglich: ${dateLong(contract.cancel_effective)}` : undefined}>
          <input className="input" id="cancel-end" type="date" min={contract.start_date} value={endDate}
            onChange={(e) => setEndDate(e.target.value)} {...describe('cancel-end', errors.end, Boolean(contract.cancel_effective))} />
        </Field>
        <Actions onCancel={onClose} busy={cancel.isPending} label="Als gekündigt markieren" busyLabel="Speichert …" error={errors.form} />
      </form>
    </Dialog>
  );
}

export function DeleteContractDialog({ contract, onClose }: { contract: Contract; onClose: () => void }) {
  const remove = useDeleteContract();
  const notify = useToast();
  const confirm = () => remove.mutate(contract.id, {
    onSuccess: () => { notify(`${contract.name} gelöscht`); onClose(); },
  });
  return (
    <Dialog title={`${contract.name} löschen?`} onClose={onClose} busy={remove.isPending}>
      <p className="muted">
        Der Vertrag wird endgültig entfernt. Wenn du ihn gekündigt hast, markiere ihn besser als gekündigt, dann bleibt er bis zum Ende sichtbar.
      </p>
      {remove.isError && <p className="err" role="alert">{remove.error.message}</p>}
      <div className="dialog-actions">
        <button className="btn" onClick={onClose} disabled={remove.isPending} data-autofocus>Abbrechen</button>
        <button className="btn btn-danger" onClick={confirm} disabled={remove.isPending}>{remove.isPending ? 'Löscht …' : 'Löschen'}</button>
      </div>
    </Dialog>
  );
}
