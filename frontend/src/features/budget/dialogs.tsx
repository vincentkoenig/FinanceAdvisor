// Dialoge des Haushaltsbuchs: Buchung hinzufügen und Buchung löschen.
import { useState, type FormEvent } from 'react';
import { type Category, useAddBooking, useCategories, useDefaultCategories, useDeleteBooking } from '../../api/budget';
import type { Booking, CategoryType } from '../../api/overview';
import { Dialog } from '../../components/Dialog';
import { Actions, type Errors, Field, apiErrors, describe, positive } from '../../components/form';
import { useToast } from '../../components/Toast';
import { eur } from '../../lib/format';

const TYPES: { type: CategoryType; label: string }[] = [
  { type: 'income', label: 'Einnahme' },
  { type: 'fixed_expense', label: 'Fixkosten' },
  { type: 'variable_expense', label: 'Variable Ausgabe' },
];

// Hauptkategorien des Typs und ihre Unterkategorien (ohne Unterkategorien ist die Hauptkategorie selbst wählbar)
function choices(categories: Category[], type: CategoryType) {
  return categories
    .filter((c) => c.type === type && c.parent_id === null)
    .map((main) => {
      const subs = categories.filter((c) => c.parent_id === main.id);
      return { main, subs: subs.length ? subs : [main] };
    });
}

export function AddBookingDialog({ defaultDate, onClose }: { defaultDate: string; onClose: () => void }) {
  const categories = useCategories();
  const defaults = useDefaultCategories();
  const add = useAddBooking();
  const notify = useToast();
  const [type, setType] = useState<CategoryType>('variable_expense');
  const [mainId, setMainId] = useState<number | null>(null);
  const [subId, setSubId] = useState<number | null>(null);
  const [amount, setAmount] = useState('');
  const [date, setDate] = useState(defaultDate);
  const [description, setDescription] = useState('');
  const [recurring, setRecurring] = useState(false);
  const [endDate, setEndDate] = useState('');
  const [errors, setErrors] = useState<Errors>({});

  const groups = choices(categories.data ?? [], type);
  // Ohne eigene Wahl die erste passende Kategorie
  const group = groups.find((g) => g.main.id === mainId) ?? groups[0];
  const sub = group?.subs.find((c) => c.id === subId) ?? group?.subs[0];

  const chooseType = (next: CategoryType) => {
    setType(next);
    setMainId(null);
    setSubId(null);
  };

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    const found: Errors = {};
    const value = positive(amount, 'einen Betrag', found, 'amount');
    if (!date) found.date = 'Bitte ein Datum wählen.';
    if (recurring && endDate && endDate < date) found.end = 'Das Ende darf nicht vor dem Start liegen.';
    if (!sub) found.form = 'Bitte eine Kategorie wählen.';
    setErrors(found);
    if (Object.keys(found).length || !sub) return;
    try {
      await add.mutateAsync({
        category_id: sub.id, amount: value, description: description.trim() || null, date,
        is_recurring: recurring, end_date: recurring && endDate ? endDate : null,
      });
      notify(`Buchung gespeichert: ${description.trim() || sub.name} ${eur(value)}`);
      onClose();
    } catch (error) {
      setErrors(apiErrors(error, { amount: 'amount', date: 'date', end_date: 'end', description: 'description', category_id: 'form' }));
    }
  };

  if (categories.isSuccess && categories.data.length === 0) {
    return (
      <Dialog title="Buchung hinzufügen" onClose={onClose} busy={defaults.isPending}>
        <p className="muted">Für Buchungen brauchst du Kategorien. FinTrack legt die üblichen an, zum Beispiel Gehalt, Miete und Lebensmittel.</p>
        {defaults.isError && <p className="err" role="alert">{defaults.error.message}</p>}
        <div className="dialog-actions">
          <button className="btn" onClick={onClose} disabled={defaults.isPending}>Abbrechen</button>
          <button className="btn btn-primary" onClick={() => defaults.mutate()} disabled={defaults.isPending} data-autofocus>
            {defaults.isPending ? 'Legt an …' : 'Kategorien anlegen'}
          </button>
        </div>
      </Dialog>
    );
  }

  return (
    <Dialog title="Buchung hinzufügen" onClose={onClose} busy={add.isPending}>
      <form className="dialog-form" onSubmit={submit} noValidate>
        <div className="segmented" role="group" aria-label="Art der Buchung">
          {TYPES.map((t) => (
            <button type="button" key={t.type} aria-pressed={type === t.type} onClick={() => chooseType(t.type)}>{t.label}</button>
          ))}
        </div>
        <Field id="booking-amount" label="Betrag" error={errors.amount}>
          <input className="input input-lg" id="booking-amount" inputMode="decimal" placeholder="0,00 €" value={amount}
            onChange={(e) => setAmount(e.target.value)} {...describe('booking-amount', errors.amount)} />
        </Field>
        <div className="form-grid">
          <Field id="booking-main" label="Kategorie">
            <select className="select" id="booking-main" value={group?.main.id ?? ''} disabled={!categories.isSuccess}
              onChange={(e) => { setMainId(Number(e.target.value)); setSubId(null); }}>
              {groups.map((g) => <option key={g.main.id} value={g.main.id}>{g.main.name}</option>)}
            </select>
          </Field>
          <Field id="booking-sub" label="Unterkategorie">
            <select className="select" id="booking-sub" value={sub?.id ?? ''} disabled={!categories.isSuccess}
              onChange={(e) => setSubId(Number(e.target.value))}>
              {group?.subs.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
          </Field>
          <Field id="booking-date" label={recurring ? 'Erstmals am' : 'Datum'} error={errors.date}>
            <input className="input" id="booking-date" type="date" value={date} onChange={(e) => setDate(e.target.value)} {...describe('booking-date', errors.date)} />
          </Field>
          <Field id="booking-description" label="Beschreibung" error={errors.description}>
            <input className="input" id="booking-description" placeholder="optional" maxLength={200} value={description}
              onChange={(e) => setDescription(e.target.value)} {...describe('booking-description', errors.description)} />
          </Field>
        </div>
        <div className="switch-row">
          <div className="text">
            <label htmlFor="booking-recurring" className="strong">Jeden Monat wiederholen</label>
            <p className="hint">Zum Beispiel Gehalt, Miete oder Abos</p>
          </div>
          <input type="checkbox" className="switch" id="booking-recurring" checked={recurring} onChange={(e) => setRecurring(e.target.checked)} />
        </div>
        {recurring && (
          <Field id="booking-end" label="Endet am" error={errors.end} hint="Leer lassen, wenn sie nicht endet">
            <input className="input" id="booking-end" type="date" min={date} value={endDate} onChange={(e) => setEndDate(e.target.value)} {...describe('booking-end', errors.end, true)} />
          </Field>
        )}
        <Actions onCancel={onClose} busy={add.isPending} label="Speichern" busyLabel="Speichert …" error={errors.form} />
      </form>
    </Dialog>
  );
}

export function DeleteBookingDialog({ booking, onClose }: { booking: Booking; onClose: () => void }) {
  const remove = useDeleteBooking();
  const notify = useToast();
  const name = booking.description || booking.category_name || 'Buchung';
  const confirm = () => remove.mutate(booking.id, {
    onSuccess: () => { notify(`${name} gelöscht`); onClose(); },
  });
  return (
    <Dialog title={`${name} löschen?`} onClose={onClose} busy={remove.isPending}>
      <p className="muted">
        {booking.is_recurring
          ? 'Die Buchung wiederholt sich jeden Monat. Gelöscht fehlt sie in allen Monaten, auch in den vergangenen. Wenn sie nur ab jetzt wegfallen soll, pausiere sie stattdessen.'
          : 'Die Buchung wird endgültig entfernt.'}
      </p>
      {remove.isError && <p className="err" role="alert">{remove.error.message}</p>}
      <div className="dialog-actions">
        <button className="btn" onClick={onClose} disabled={remove.isPending} data-autofocus>Abbrechen</button>
        <button className="btn btn-danger" onClick={confirm} disabled={remove.isPending}>{remove.isPending ? 'Löscht …' : 'Löschen'}</button>
      </div>
    </Dialog>
  );
}
