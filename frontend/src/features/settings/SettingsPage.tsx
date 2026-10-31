// Einstellungen: Anlageprofil (für KI-Berater und Analyse), Darstellung auf diesem Gerät,
// eigene Daten exportieren/importieren und das Konto.
import { useState, type FormEvent } from 'react';
import { useNavigate, useOutletContext } from 'react-router';
import { useLogout, useMe, type User } from '../../api/auth';
import { ApiError } from '../../api/client';
import { useImportData, useSaveProfile, type ImportCounts } from '../../api/settings';
import { Icon } from '../../components/Icon';
import type { RootContext } from '../../components/Shell';
import { useToast } from '../../components/Toast';
import { parseAmount } from '../../lib/format';
import { usePrivacy } from '../../lib/privacy';

const RISK = [['conservative', 'Konservativ'], ['balanced', 'Ausgewogen'], ['aggressive', 'Aggressiv']];
const EXPERIENCE = [['beginner', 'Anfänger'], ['intermediate', 'Fortgeschritten'], ['expert', 'Experte']];
const HORIZON = [['short-term', 'Kurzfristig'], ['medium-term', 'Mittelfristig'], ['long-term', 'Langfristig']];

function Row({ title, description, children }: { title: string; description: string; children: React.ReactNode }) {
  const id = `s-${title.toLowerCase().replace(/\W+/g, '-')}`;
  return (
    <section className="settings-row" aria-labelledby={id}>
      <div className="label-col"><h2 id={id}>{title}</h2><p>{description}</p></div>
      <div className="panel">{children}</div>
    </section>
  );
}

function Select({ id, label, options, value, onChange }: {
  id: string; label: string; options: string[][]; value: string; onChange: (value: string) => void;
}) {
  return (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      <select className="select" id={id} value={value} onChange={(e) => onChange(e.target.value)}>
        <option value="">Nicht angegeben</option>
        {options.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
      </select>
    </div>
  );
}

const budgetText = (value: number | null) =>
  value === null ? '' : new Intl.NumberFormat('de-DE', { maximumFractionDigits: 2 }).format(value);

function ProfileForm({ user }: { user: User }) {
  const save = useSaveProfile();
  const notify = useToast();
  const [risk, setRisk] = useState(user.risk_profile ?? '');
  const [experience, setExperience] = useState(user.investment_experience ?? '');
  const [horizon, setHorizon] = useState(user.investment_horizon ?? '');
  const [budget, setBudget] = useState(budgetText(user.monthly_budget));
  const [budgetError, setBudgetError] = useState('');

  const submit = (event: FormEvent) => {
    event.preventDefault();
    const amount = parseAmount(budget);
    if (amount !== null && (Number.isNaN(amount) || amount <= 0)) {
      setBudgetError('Bitte einen Betrag größer 0 eingeben, z. B. 500 oder 250,50.');
      return;
    }
    setBudgetError('');
    save.mutate(
      { risk_profile: risk || null, investment_experience: experience || null, monthly_budget: amount, investment_horizon: horizon || null },
      {
        onSuccess: () => notify('Anlageprofil gespeichert'),
        onError: (error) => {
          if (error instanceof ApiError && error.fields.monthly_budget) setBudgetError(error.fields.monthly_budget);
          else notify(error.message, { error: true });
        },
      },
    );
  };

  return (
    <form className="form-grid" onSubmit={submit} noValidate>
      <Select id="risk" label="Risikoprofil" options={RISK} value={risk} onChange={setRisk} />
      <Select id="experience" label="Erfahrung" options={EXPERIENCE} value={experience} onChange={setExperience} />
      <div className="field">
        <label htmlFor="budget">Monatlich investierbar (€)</label>
        <input className="input num" id="budget" inputMode="decimal" placeholder="z. B. 500" value={budget}
          onChange={(e) => setBudget(e.target.value)} aria-invalid={budgetError ? true : undefined}
          aria-describedby={budgetError ? 'budget-error' : undefined} />
        {budgetError && <p className="err" id="budget-error">{budgetError}</p>}
      </div>
      <Select id="horizon" label="Anlagehorizont" options={HORIZON} value={horizon} onChange={setHorizon} />
      <div className="full form-actions">
        <button className="btn btn-primary" type="submit" disabled={save.isPending}>{save.isPending ? 'Speichert …' : 'Speichern'}</button>
      </div>
    </form>
  );
}

const COUNT_LABELS: [string, string][] = [
  ['transactions', 'Buchungen'], ['positions', 'Positionen'], ['categories', 'Kategorien'], ['savings_plans', 'Sparpläne'],
];

function importSummary(counts: ImportCounts) {
  return COUNT_LABELS.map(([key, label]) => `${counts[key] ?? 0} ${label}`).join(', ');
}

function DataSection() {
  const importData = useImportData();
  const notify = useToast();
  // Gelesene Datei, die noch bestätigt werden muss
  const [pending, setPending] = useState<{ name: string; payload: unknown } | null>(null);
  const [inputKey, setInputKey] = useState(0);

  const pick = async (file: File | undefined) => {
    if (!file) return;
    try {
      setPending({ name: file.name, payload: JSON.parse(await file.text()) });
    } catch {
      notify('Die Datei ist keine gültige Exportdatei.', { error: true });
      setInputKey((k) => k + 1);
    }
  };

  const close = () => { setPending(null); setInputKey((k) => k + 1); };

  const confirm = () => importData.mutate(pending!.payload, {
    onSuccess: (data) => { notify(`Importiert: ${importSummary(data.imported)}`); close(); },
    onError: (error) => { notify(error.message, { error: true }); close(); },
  });

  return (
    <>
      <div className="switch-row">
        <div className="text">
          <span className="strong">Exportieren</span>
          <p className="hint">Die Datei enthält deine Finanzdaten im Klartext. Bewahre sie sicher auf.</p>
        </div>
        <a className="btn btn-sm" href="/api/v1/me/export" download><Icon name="download" size={16} />Herunterladen</a>
      </div>
      <div className="switch-row">
        <div className="text">
          <span className="strong">Importieren</span>
          <p className="hint">Nur in ein leeres Konto, z. B. nach einem Umzug auf einen neuen Server.</p>
        </div>
        <label className="btn btn-sm" htmlFor="import-file"><Icon name="upload" size={16} />Datei wählen</label>
        <input key={inputKey} className="sr-only" type="file" id="import-file" accept="application/json,.json"
          onChange={(e) => pick(e.target.files?.[0])} />
      </div>

      {pending && (
        <div className="overlay overlay-center" onClick={(e) => e.target === e.currentTarget && !importData.isPending && close()}>
          <div className="dialog" role="dialog" aria-modal="true" aria-labelledby="import-title" aria-describedby="import-text">
            <h2 id="import-title">Daten importieren?</h2>
            <p id="import-text" className="muted">
              Die Daten aus <b className="strong">{pending.name}</b> werden in dein Konto übernommen. Das geht nur, solange
              dein Konto noch keine eigenen Daten enthält.
            </p>
            <div className="dialog-actions">
              <button className="btn" onClick={close} disabled={importData.isPending} autoFocus>Abbrechen</button>
              <button className="btn btn-primary" onClick={confirm} disabled={importData.isPending}>
                {importData.isPending ? 'Importiert …' : 'Importieren'}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

export function SettingsPage() {
  const { theme, setTheme } = useOutletContext<RootContext>();
  const { data: user } = useMe();
  const { hidden, setHidden } = usePrivacy();
  const logout = useLogout();
  const navigate = useNavigate();
  if (!user) return null;

  const signOut = () => logout.mutate(undefined, { onSettled: () => navigate('/login', { replace: true }) });

  return (
    <>
      <div className="title-row">
        <div className="text"><h1>Einstellungen</h1><p className="sub">{user.email}</p></div>
      </div>
      <div>
        <Row title="Anlageprofil" description="Fließt in jede Antwort des KI-Beraters und in die Portfolio-Analyse ein.">
          <ProfileForm user={user} />
        </Row>
        <Row title="Darstellung" description="Gilt auf diesem Gerät. Das Handy kann ein anderes Design haben als der Laptop.">
          <div className="field">
            <span className="label" id="theme-label">Design</span>
            <div className="segmented" role="group" aria-labelledby="theme-label">
              <button type="button" aria-pressed={theme === 'dark'} onClick={() => setTheme('dark')}>Dunkel</button>
              <button type="button" aria-pressed={theme === 'light'} onClick={() => setTheme('light')}>Hell</button>
            </div>
          </div>
          <div className="switch-row">
            <div className="text">
              <label htmlFor="hide-amounts" className="strong">Beträge verbergen</label>
              <p className="hint">Zeigt Euro-Beträge und Stückzahlen als •••• an, Prozente bleiben sichtbar. Auch über das Auge oben in der Leiste.</p>
            </div>
            <input type="checkbox" className="switch" id="hide-amounts" checked={hidden} onChange={(e) => setHidden(e.target.checked)} />
          </div>
        </Row>
        <Row title="Meine Daten" description="Eine Datei mit allem: Buchungen, Kategorien, Portfolio, Käufe und Verkäufe, Sparpläne, Watchlist, Dividenden, Chats und Analysen.">
          <DataSection />
        </Row>
        <Row title="Konto" description="Neue Konten legt der Betreiber an, eine Registrierung gibt es nicht.">
          <div className="switch-row">
            <div className="text">
              <span className="strong">{user.email}</span>
              <p className="hint">Auf diesem Gerät angemeldet</p>
            </div>
            <button className="btn btn-sm" onClick={signOut} disabled={logout.isPending}><Icon name="logout" size={16} />Abmelden</button>
          </div>
        </Row>
      </div>
    </>
  );
}
