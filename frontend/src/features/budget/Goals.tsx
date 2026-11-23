// Sparziele als Töpfe vom Kontostand: Das Geld bleibt auf dem Konto und wird nur gedanklich zurückgelegt.
// Im Haushaltsbuch: Liste mit Fortschritt und Plan, anlegen, ändern, einzahlen, entnehmen, löschen.
// Auf der Übersicht steht nur der Fortschritt (GoalBars).
import { useState, type FormEvent } from 'react';
import { type Goal, useAddGoal, useDeleteGoal, useGoalEntry, useGoals, useUpdateGoal } from '../../api/goals';
import { Dialog } from '../../components/Dialog';
import { Actions, type Errors, Field, apiErrors, describe, positive } from '../../components/form';
import { Icon } from '../../components/Icon';
import { useToast } from '../../components/Toast';
import { dayShort, parseAmount } from '../../lib/format';
import { useMoney } from '../../lib/privacy';

type Open = { type: 'add' } | { type: 'edit'; goal: Goal } | { type: 'entry'; goal: Goal } | null;

const field = (value: number | null | undefined) =>
  value ? value.toLocaleString('de-DE', { maximumFractionDigits: 2, useGrouping: false }) : '';

/** Kurztext zum Plan: "im Plan", "120 € pro Monat zu wenig" ... */
export function planText(goal: Goal, eur: (value: number) => string) {
  if (goal.reached) return 'Ziel erreicht';
  if (!goal.plan) return goal.monthly_amount ? `${eur(goal.monthly_amount)} pro Monat` : `noch ${eur(goal.missing)}`;
  if (goal.plan.status === 'overdue') return `Termin vorbei, noch ${eur(goal.missing)}`;
  if (goal.plan.status === 'on_track') return `im Plan bis ${dayShort(goal.target_date!)}`;
  return `${eur(goal.plan.shortfall_monthly ?? goal.plan.needed_monthly)} pro Monat zu wenig für ${dayShort(goal.target_date!)}`;
}

// Farbe der Plan-Zeile: rot, wenn das Ziel hinter dem Plan liegt, grün, wenn es erreicht ist
const tone = (goal: Goal) => (goal.plan?.status === 'behind' || goal.plan?.status === 'overdue' ? 'neg' : goal.reached ? 'pos' : '');

function Bar({ goal }: { goal: Goal }) {
  return (
    <div className="goal-track" role="meter" aria-label={`Fortschritt ${goal.name}`} aria-valuemin={0}
      aria-valuemax={goal.target_amount} aria-valuenow={goal.balance}>
      <span className={goal.reached ? 'done' : ''} style={{ width: `${goal.progress * 100}%` }} />
    </div>
  );
}

/** Kompakte Fortschrittsbalken für die Übersicht */
export function GoalBars({ goals }: { goals: Goal[] }) {
  const { eur } = useMoney();
  return (
    <div className="goal-list">
      {goals.map((goal) => (
        <div className="goal" key={goal.id}>
          <div className="goal-head">
            <span className="trunc">{goal.name}</span>
            <span className="num muted">{eur(goal.balance)} / {eur(goal.target_amount)}</span>
          </div>
          <Bar goal={goal} />
          <span className="sub-line"><span className={tone(goal)}>{planText(goal, eur)}</span></span>
        </div>
      ))}
    </div>
  );
}

export function GoalsSection() {
  const { eur } = useMoney();
  const goals = useGoals();
  const [open, setOpen] = useState<Open>(null);
  const close = () => setOpen(null);
  const data = goals.data;

  return (
    <section className="panel" aria-labelledby="h-goals" id="goals">
      <div className="panel-head">
        <h2 id="h-goals">Sparziele</h2>
        {data && data.goals.length > 0 && <span className="meta num">{eur(data.total)} zurückgelegt</span>}
        <button className="btn btn-sm" onClick={() => setOpen({ type: 'add' })}><Icon name="plus" size={16} />Sparziel</button>
      </div>
      {data && data.over_by > 0 && (
        <p className="err goal-warning" role="alert">
          In den Töpfen liegen {eur(data.over_by)} mehr, als auf dem Konto sind ({eur(data.cash_balance ?? 0)}).
        </p>
      )}
      {data && data.goals.length === 0 && (
        <p className="empty-line">Leg Geld gedanklich zurück, zum Beispiel für Urlaub oder einen Notgroschen. Es bleibt auf deinem Konto.</p>
      )}
      {data && data.goals.length > 0 && (
        <div className="goal-list">
          {data.goals.map((goal) => (
            <div className="goal" key={goal.id}>
              <div className="goal-head">
                <button className="plain-btn strong trunc" onClick={() => setOpen({ type: 'edit', goal })} aria-label={`${goal.name} bearbeiten`}>{goal.name}</button>
                <span className="num">{eur(goal.balance)} <span className="muted">/ {eur(goal.target_amount)}</span></span>
              </div>
              <Bar goal={goal} />
              <div className="goal-foot">
                <span className="sub-line"><span className={tone(goal)}>{planText(goal, eur)}</span></span>
                <button className="btn btn-sm" onClick={() => setOpen({ type: 'entry', goal })} aria-label={`${goal.name}: einzahlen oder entnehmen`}>
                  Ein-/Auszahlen
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
      {open?.type === 'add' && <GoalDialog onClose={close} />}
      {open?.type === 'edit' && <GoalDialog goal={open.goal} onClose={close} />}
      {open?.type === 'entry' && <EntryDialog goal={open.goal} onClose={close} />}
    </section>
  );
}

function GoalDialog({ goal, onClose }: { goal?: Goal; onClose: () => void }) {
  const add = useAddGoal();
  const update = useUpdateGoal();
  const remove = useDeleteGoal();
  const notify = useToast();
  const [name, setName] = useState(goal?.name ?? '');
  const [target, setTarget] = useState(field(goal?.target_amount));
  const [date, setDate] = useState(goal?.target_date ?? '');
  const [monthly, setMonthly] = useState(field(goal?.monthly_amount));
  const [start, setStart] = useState('');
  const [errors, setErrors] = useState<Errors>({});
  const busy = add.isPending || update.isPending || remove.isPending;

  const optional = (text: string, key: string, found: Errors) => {
    if (!text.trim()) return null;
    const value = parseAmount(text);
    if (value === null || Number.isNaN(value) || value < 0) { found[key] = 'Bitte einen Betrag ab 0 eingeben.'; return null; }
    return value || null;
  };

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    const found: Errors = {};
    if (!name.trim()) found.name = 'Bitte einen Namen eingeben.';
    const targetAmount = positive(target, 'einen Zielbetrag', found, 'target');
    const monthlyAmount = optional(monthly, 'monthly', found);
    const startAmount = goal ? null : optional(start, 'start', found);
    setErrors(found);
    if (Object.keys(found).length) return;
    const body = { name: name.trim(), target_amount: targetAmount, target_date: date || null, monthly_amount: monthlyAmount };
    try {
      const result = goal ? await update.mutateAsync({ id: goal.id, ...body }) : await add.mutateAsync({ ...body, start_amount: startAmount });
      notify(result.message);
      onClose();
    } catch (error) {
      setErrors(apiErrors(error, { name: 'name', target_amount: 'target', target_date: 'date', monthly_amount: 'monthly', start_amount: 'start' }));
    }
  };

  const del = () => goal && remove.mutate(goal.id, {
    onSuccess: (result) => { notify(result.message); onClose(); },
    onError: (error) => setErrors({ form: error.message }),
  });

  return (
    <Dialog title={goal ? 'Sparziel bearbeiten' : 'Sparziel anlegen'} onClose={onClose} busy={busy}>
      <form className="dialog-form" onSubmit={submit} noValidate>
        <Field id="goal-name" label="Name" error={errors.name}>
          <input className="input" id="goal-name" placeholder="z. B. Urlaub" value={name} maxLength={100}
            onChange={(e) => setName(e.target.value)} {...describe('goal-name', errors.name)} />
        </Field>
        <div className="form-grid">
          <Field id="goal-target" label="Zielbetrag" error={errors.target}>
            <input className="input num" id="goal-target" inputMode="decimal" placeholder="0,00 €" value={target}
              onChange={(e) => setTarget(e.target.value)} {...describe('goal-target', errors.target)} />
          </Field>
          <Field id="goal-date" label="Bis wann (optional)" error={errors.date}>
            <input className="input" id="goal-date" type="date" value={date} onChange={(e) => setDate(e.target.value)} {...describe('goal-date', errors.date)} />
          </Field>
          <Field id="goal-monthly" label="Pro Monat (optional)" error={errors.monthly}
            hint={goal ? 'Eine geänderte Rate gilt ab nächstem Monat.' : 'Kommt jeden Monat automatisch dazu.'}>
            <input className="input num" id="goal-monthly" inputMode="decimal" placeholder="0,00 €" value={monthly}
              onChange={(e) => setMonthly(e.target.value)} {...describe('goal-monthly', errors.monthly, true)} />
          </Field>
          {!goal && (
            <Field id="goal-start" label="Schon zurückgelegt (optional)" error={errors.start}>
              <input className="input num" id="goal-start" inputMode="decimal" placeholder="0,00 €" value={start}
                onChange={(e) => setStart(e.target.value)} {...describe('goal-start', errors.start)} />
            </Field>
          )}
        </div>
        <p className="hint">Das Geld bleibt auf deinem Konto. Der Topf legt es nur gedanklich zurück.</p>
        {goal && (
          <button type="button" className="btn btn-sm goal-delete" onClick={del} disabled={busy}>
            <Icon name="trash" size={16} />Sparziel löschen
          </button>
        )}
        <Actions onCancel={onClose} busy={busy} label={goal ? 'Speichern' : 'Anlegen'} busyLabel="Speichert …" error={errors.form} />
      </form>
    </Dialog>
  );
}

function EntryDialog({ goal, onClose }: { goal: Goal; onClose: () => void }) {
  const { eur } = useMoney();
  const entry = useGoalEntry();
  const notify = useToast();
  const [kind, setKind] = useState<'in' | 'out'>('in');
  const [amount, setAmount] = useState('');
  const [note, setNote] = useState('');
  const [errors, setErrors] = useState<Errors>({});

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    const found: Errors = {};
    const value = positive(amount, 'einen Betrag', found, 'amount');
    if (kind === 'out' && value > goal.balance + 0.005) found.amount = `Im Topf sind nur ${eur(goal.balance)}.`;
    setErrors(found);
    if (Object.keys(found).length) return;
    try {
      const result = await entry.mutateAsync({ id: goal.id, amount: kind === 'in' ? value : -value, note: note.trim() || null });
      notify(result.message);
      onClose();
    } catch (error) {
      setErrors(apiErrors(error, { amount: 'amount', note: 'note' }));
    }
  };

  return (
    <Dialog title={goal.name} onClose={onClose} busy={entry.isPending}>
      <form className="dialog-form" onSubmit={submit} noValidate>
        <p className="muted dialog-sub">Im Topf: {eur(goal.balance)} von {eur(goal.target_amount)}</p>
        <div className="segmented" role="group" aria-label="Richtung">
          <button type="button" aria-pressed={kind === 'in'} onClick={() => setKind('in')}>Einzahlen</button>
          <button type="button" aria-pressed={kind === 'out'} onClick={() => setKind('out')}>Entnehmen</button>
        </div>
        <Field id="entry-amount" label="Betrag" error={errors.amount}>
          <input className="input input-lg" id="entry-amount" inputMode="decimal" placeholder="0,00 €" value={amount}
            onChange={(e) => setAmount(e.target.value)} {...describe('entry-amount', errors.amount)} />
        </Field>
        <Field id="entry-note" label="Notiz (optional)" error={errors.note}>
          <input className="input" id="entry-note" maxLength={200} value={note} onChange={(e) => setNote(e.target.value)} />
        </Field>
        <Actions onCancel={onClose} busy={entry.isPending} label={kind === 'in' ? 'Einzahlen' : 'Entnehmen'} busyLabel="Speichert …" error={errors.form} />
      </form>
    </Dialog>
  );
}
