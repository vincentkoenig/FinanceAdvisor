// Umsätze importieren. Frage der Seite: Welche Umsätze aus dem Bankexport sollen ins Haushaltsbuch?
// CSV-Export oder Kontoauszug als PDF wählen → (bei CSV Spalten zuordnen, falls nicht erkannt) →
// Vorschau prüfen: neue Umsätze nach Empfänger gruppiert, Kategorie je Gruppe (Vorschläge aus früheren Buchungen,
// Regeln und bekannten Händlern, fehlende auf Wunsch von der KI, neue Kategorien direkt hier) → übernehmen.
// Gespeichert wird erst beim Übernehmen; die Datei selbst bleibt nirgends liegen.
import { useState, type FormEvent } from 'react';
import { Link, useNavigate } from 'react-router';
import { type Category, useAddCategory, useCategories } from '../../api/budget';
import {
  type ColumnMapping, type ImportPreview, type ImportRow, UnknownColumnsError, useCategorizeBankImport, useCommitBankImport, usePreviewBankImport,
} from '../../api/imports';
import { Dialog } from '../../components/Dialog';
import { Icon } from '../../components/Icon';
import { useToast } from '../../components/Toast';
import { dayShort, parseDay } from '../../lib/format';
import { useMoney } from '../../lib/privacy';
import {
  MAPPING_FIELDS, type Choice, type Group, type GroupFilter, type Proposal, applySuggestions, assignCategory, assignRest, assignToPayees,
  categoryOptions, groupRows, initialChoices, payeesWithoutCategory, proposalsFrom, setGroupCategory, setGroupSelected, toCommit,
  visibleGroups,
} from './importModel';

export function ImportPage() {
  const previewImport = usePreviewBankImport();
  const commit = useCommitBankImport();
  const categorize = useCategorizeBankImport();
  const addCategory = useAddCategory();
  const categories = useCategories();
  const notify = useToast();
  const navigate = useNavigate();
  const [file, setFile] = useState<File | null>(null);
  const [inputKey, setInputKey] = useState(0);
  const [columns, setColumns] = useState<string[] | null>(null);
  const [mapping, setMapping] = useState<ColumnMapping>({});
  const [preview, setPreview] = useState<ImportPreview | null>(null);
  const [choices, setChoices] = useState<Record<string, Choice>>({});
  const [error, setError] = useState<string | null>(null);
  // Von der KI vorgeschlagene neue Kategorien und die Zeile, für die gerade eine neue angelegt wird
  const [proposals, setProposals] = useState<Proposal[]>([]);
  // Für wen gerade eine neue Kategorie angelegt wird (eine Zeile oder eine ganze Gruppe)
  const [creatingFor, setCreatingFor] = useState<{ income: boolean; apply: (id: number) => void } | null>(null);
  const [filter, setFilter] = useState<GroupFilter>({ direction: 'all', onlyMissing: false, sort: 'count' });
  const [open, setOpen] = useState<Record<string, boolean>>({});
  const [restOpen, setRestOpen] = useState(false);

  const load = (chosen: File, withMapping?: ColumnMapping) => {
    setError(null);
    previewImport.mutate({ file: chosen, mapping: withMapping }, {
      onSuccess: (result) => {
        setPreview(result);
        setChoices(initialChoices(result.rows));
        setColumns(null);
      },
      onError: (failure) => {
        setPreview(null);
        if (failure instanceof UnknownColumnsError && failure.columns.length) setColumns(failure.columns);
        setError(failure.message);
      },
    });
  };

  const pick = (chosen: File | undefined) => {
    if (!chosen) return;
    setFile(chosen);
    setMapping({});
    setColumns(null);
    load(chosen);
  };

  const reset = () => {
    setFile(null);
    setPreview(null);
    setProposals([]);
    setColumns(null);
    setError(null);
    setInputKey((k) => k + 1);
  };

  const summary = preview ? toCommit(preview.rows, choices) : null;
  const groups = preview ? groupRows(preview.rows, choices) : [];
  const shown = visibleGroups(groups, filter);
  const others = preview ? preview.rows.filter((r) => r.status !== 'new') : [];
  const openPayees = preview ? payeesWithoutCategory(preview.rows, choices) : [];

  const suggest = () => {
    if (!preview || !openPayees.length) return;
    setError(null);
    categorize.mutate(openPayees, {
      onSuccess: ({ suggestions }) => {
        const result = applySuggestions(preview.rows, choices, suggestions);
        const proposed = proposalsFrom(suggestions, preview.rows, result.choices);
        setChoices(result.choices);
        setProposals(proposed);
        const extra = proposed.length ? `, ${proposed.length === 1 ? '1 neue Kategorie' : `${proposed.length} neue Kategorien`} vorgeschlagen` : '';
        notify(result.filled || proposed.length ? `${result.filled} Umsätze vorbelegt${extra}, bitte kurz prüfen` : 'Die KI hatte keine sicheren Vorschläge');
      },
      onError: (failure) => setError(failure.message),
    });
  };
  // Vorgeschlagene Kategorie anlegen und allen Umsätzen ihrer Empfänger ohne Kategorie geben
  const accept = (proposal: Proposal) => {
    const parent = categories.data?.find((c) => c.id === proposal.parent_id);
    if (!preview || !parent) return;
    addCategory.mutate({ name: proposal.name, type: parent.type, parent_id: parent.id }, {
      onSuccess: ({ category_id }) => {
        const result = assignToPayees(preview.rows, choices, proposal.payees, category_id);
        setChoices(result.choices);
        setProposals((list) => list.filter((p) => p.key !== proposal.key));
        notify(`${proposal.parent_name} · ${proposal.name} angelegt, ${result.filled} Umsätze zugeordnet`);
      },
      onError: (failure) => notify(failure.message, { error: true }),
    });
  };

  const save = () => {
    if (!summary || summary.missing || !summary.commit.length) return;
    commit.mutate(summary.commit, {
      onSuccess: (result) => {
        notify(result.skipped ? `${result.message}, ${result.skipped} waren schon da` : result.message);
        navigate('/budget');
      },
      onError: (failure) => setError(failure.message),
    });
  };

  return (
    <>
      <div className="title-row">
        <div className="text">
          <h1>Umsätze importieren</h1>
          <p className="sub">CSV-Export deiner Bank. Vor dem Speichern siehst du alles in einer Vorschau.</p>
        </div>
        <div className="actions">
          <Link to="/budget" className="btn"><Icon name="left" size={16} />Haushaltsbuch</Link>
        </div>
      </div>

      <section className="panel" aria-labelledby="h-file">
        <div className="panel-head"><h2 id="h-file">Datei</h2></div>
        <div className="file-row">
          <label className="btn btn-primary" htmlFor="bank-file"><Icon name="upload" size={16} />{file ? 'Andere Datei' : 'Datei wählen'}</label>
          <input key={inputKey} className="sr-only" type="file" id="bank-file" accept=".csv,text/csv,text/plain,.pdf,application/pdf"
            onChange={(e) => pick(e.target.files?.[0])} disabled={previewImport.isPending || commit.isPending} />
          <span className="muted trunc">{previewImport.isPending ? 'Liest …' : file?.name ?? 'CSV-Export (Umsätze → Export) oder Kontoauszug als PDF'}</span>
        </div>
        <p className="hint">
          Die Datei wird nur gelesen und nicht gespeichert. Umsätze, die schon im Haushaltsbuch stehen, werden erkannt.
          CSV liest FinTrack selbst; bei einem PDF werden zuerst dein Name, deine Adresse, IBANs sowie Konto- und
          Kundennummern entfernt, den Rest liest OpenAI aus.
        </p>
        {preview?.sent_text !== undefined && (
          <details className="sent-details">
            <summary>Gesendeter Text{preview.note ? ` · ${preview.note}` : ''}</summary>
            <pre className="sent-text">{preview.sent_text}</pre>
          </details>
        )}
        {/* Mit Vorschau steht der Fehler dort, nicht zweimal */}
        {error && !columns && !preview && <p className="err" role="alert">{error}</p>}
      </section>

      {columns && file && (
        <section className="panel" aria-labelledby="h-columns">
          <div className="panel-head"><h2 id="h-columns">Spalten zuordnen</h2></div>
          <p className="muted">{error} Wähle, in welcher Spalte was steht. Für den Betrag reicht eine Spalte mit Vorzeichen oder Soll und Haben.</p>
          <div className="form-grid">
            {MAPPING_FIELDS.map(({ field, label }) => (
              <div className="field" key={field}>
                <label htmlFor={`map-${field}`}>{label}</label>
                <select className="select" id={`map-${field}`} value={mapping[field] ?? ''}
                  onChange={(e) => setMapping((m) => {
                    const next = { ...m };
                    if (e.target.value === '') delete next[field]; else next[field] = Number(e.target.value);
                    return next;
                  })}>
                  <option value="">nicht vorhanden</option>
                  {columns.map((name, index) => <option key={index} value={index}>{name || `Spalte ${index + 1}`}</option>)}
                </select>
              </div>
            ))}
          </div>
          <div className="dialog-actions">
            <button className="btn" onClick={reset}>Abbrechen</button>
            <button className="btn btn-primary" onClick={() => load(file, mapping)} disabled={previewImport.isPending}>
              {previewImport.isPending ? 'Liest …' : 'Vorschau laden'}
            </button>
          </div>
        </section>
      )}

      {preview && (
        <section className="panel" aria-labelledby="h-preview">
          <div className="panel-head">
            <h2 id="h-preview">Vorschau</h2>
            <span className="meta">
              {[`${preview.counts.new} neu`, preview.counts.covered && `${preview.counts.covered} schon erfasst`,
                preview.counts.duplicate && `${preview.counts.duplicate} schon importiert`,
                preview.skipped.length && `${preview.skipped.length} übersprungen`].filter(Boolean).join(' · ')}
            </span>
          </div>
          {openPayees.length > 0 && (
            <div className="import-suggest">
              <button className="btn" onClick={suggest} disabled={categorize.isPending || commit.isPending}>
                <Icon name="spark" size={16} />{categorize.isPending ? 'Ordnet zu …' : 'Kategorien vorschlagen lassen'}
              </button>
              <p className="hint">
                Für {openPayees.length === 1 ? '1 Empfänger' : `${openPayees.length} Empfänger`} ohne Kategorie. An OpenAI gehen
                nur die Namen der Empfänger und ob es eine Einnahme oder Ausgabe ist, keine Beträge, Daten oder IBANs. Unsichere
                Fälle und Überweisungen auf eigene Konten bleiben leer.
              </p>
            </div>
          )}
          {proposals.length > 0 && (
            <div className="import-proposals" role="group" aria-label="Vorgeschlagene neue Kategorien">
              <p className="strong">Neue Kategorien vorgeschlagen</p>
              <p className="hint">Für diese Empfänger passt keine deiner Kategorien. Angelegt wird erst mit deinem Klick.</p>
              {proposals.map((p) => (
                <div className="row" key={p.key}>
                  <div className="grow">
                    <span className="trunc">{p.parent_name} · {p.name}</span>
                    <span className="sub-line trunc">
                      {p.rows === 1 ? '1 Umsatz' : `${p.rows} Umsätze`} · {p.payees.map((x) => x.name).join(', ')}
                    </span>
                  </div>
                  <button className="btn btn-sm" onClick={() => accept(p)} disabled={addCategory.isPending}
                    aria-label={`${p.parent_name} · ${p.name} anlegen und zuordnen`}>Anlegen und zuordnen</button>
                  <button className="icon-btn" onClick={() => setProposals((list) => list.filter((x) => x.key !== p.key))}
                    aria-label={`Vorschlag ${p.parent_name} · ${p.name} verwerfen`} title="Verwerfen"><Icon name="close" size={16} /></button>
                </div>
              ))}
            </div>
          )}
          <div className="import-toolbar">
            <div className="segmented" role="group" aria-label="Richtung">
              {([['all', 'Alle'], ['expense', 'Ausgaben'], ['income', 'Einnahmen']] as const).map(([value, label]) => (
                <button type="button" key={value} aria-pressed={filter.direction === value}
                  onClick={() => setFilter((f) => ({ ...f, direction: value }))}>
                  {label} ({groups.filter((g) => value === 'all' || (value === 'income') === g.income).length})
                </button>
              ))}
            </div>
            <label className="check-label">
              <input type="checkbox" className="check" checked={filter.onlyMissing}
                onChange={(e) => setFilter((f) => ({ ...f, onlyMissing: e.target.checked }))} />
              Nur ohne Kategorie ({groups.filter((g) => g.missing > 0).length})
            </label>
            <select className="select select-sm" aria-label="Sortieren" value={filter.sort}
              onChange={(e) => setFilter((f) => ({ ...f, sort: e.target.value as GroupFilter['sort'] }))}>
              <option value="count">Meiste Umsätze zuerst</option>
              <option value="amount">Größter Betrag zuerst</option>
              <option value="name">Nach Name</option>
            </select>
            {summary!.missing > 0 && (
              <button className="btn btn-sm" onClick={() => setRestOpen(true)}>Rest zuordnen …</button>
            )}
          </div>
          <div className="rows">
            {shown.map((group) => (
              <GroupRow key={group.key} group={group} categories={categories.data ?? []} open={Boolean(open[group.key])}
                onToggle={() => setOpen((o) => ({ ...o, [group.key]: !o[group.key] }))}
                onSelect={(selected) => setChoices((c) => setGroupSelected(group, c, selected))}
                onCategory={(category) => setChoices((c) => setGroupCategory(group, c, category))}
                onNewCategory={() => setCreatingFor({ income: group.income, apply: (id) => setChoices((c) => setGroupCategory(group, c, id)) })}>
                {group.rows.map((row) => (
                  <PreviewRow key={row.key} row={row} choice={choices[row.key]} categories={categories.data ?? []}
                    onSelect={(selected) => setChoices((c) => ({ ...c, [row.key]: { ...c[row.key], selected } }))}
                    onCategory={(category) => setChoices((c) => ({ ...c, [row.key]: { ...c[row.key], category } }))}
                    onNewCategory={() => setCreatingFor({ income: row.amount > 0, apply: (id) => setChoices((c) => assignCategory(preview.rows, c, row.key, id)) })} />
                ))}
              </GroupRow>
            ))}
            {shown.length === 0 && <p className="empty-line">Keine Empfänger für diesen Filter.</p>}
          </div>
          {others.length > 0 && (
            <details className="import-others">
              <summary>Schon erfasst oder importiert ({others.length})</summary>
              <div className="rows">
                {others.map((row) => (
                  <PreviewRow key={row.key} row={row} choice={choices[row.key]} categories={categories.data ?? []}
                    onSelect={() => {}} onCategory={() => {}} onNewCategory={() => {}} />
                ))}
              </div>
            </details>
          )}
          {preview.skipped.length > 0 && (
            <p className="hint">Übersprungen: {preview.skipped.map((s) => `Zeile ${s.line} (${s.reason})`).join(', ')}</p>
          )}
          {summary!.missing > 0 && <p className="err">Bei {summary!.missing} ausgewählten Umsätzen fehlt noch die Kategorie.</p>}
          {error && <p className="err" role="alert">{error}</p>}
          <div className="dialog-actions">
            <button className="btn" onClick={reset} disabled={commit.isPending}>Verwerfen</button>
            <button className="btn btn-primary" onClick={save} disabled={commit.isPending || summary!.missing > 0 || summary!.total === 0}>
              {commit.isPending ? 'Speichert …' : summary!.total === 1 ? '1 Umsatz übernehmen' : `${summary!.total} Umsätze übernehmen`}
            </button>
          </div>
        </section>
      )}
      {creatingFor && (
        <NewCategoryDialog income={creatingFor.income} categories={categories.data ?? []} onClose={() => setCreatingFor(null)}
          onCreated={creatingFor.apply} />
      )}
      {restOpen && preview && (
        <RestDialog categories={categories.data ?? []} rows={preview.rows} choices={choices} onClose={() => setRestOpen(false)}
          onApply={(expense, income) => {
            const result = assignRest(preview.rows, choices, expense, income);
            setChoices(result.choices);
            notify(`${result.filled} Umsätze zugeordnet`);
            setRestOpen(false);
          }} />
      )}
    </>
  );
}

const SOURCE_LABEL = { learned: 'wie zuletzt', rule: 'Regel', merchant: 'Händler' } as const;
const period = (first: string, last: string) => {
  const month = (iso: string) => parseDay(iso).toLocaleDateString('de-DE', { month: 'short', year: 'numeric' });
  return month(first) === month(last) ? month(first) : `${month(first)} – ${month(last)}`;
};

type GroupProps = {
  group: Group;
  categories: Category[];
  open: boolean;
  onToggle: () => void;
  onSelect: (selected: boolean) => void;
  onCategory: (category: number | null) => void;
  onNewCategory: () => void;
  children: React.ReactNode;
};

/** Ein Empfänger mit allen seinen neuen Umsätzen: eine Kategorie für alle, aufklappbar für Einzelne */
function GroupRow({ group, categories, open, onToggle, onSelect, onCategory, onNewCategory, children }: GroupProps) {
  const { eur } = useMoney();
  const count = group.rows.length;
  const all = group.selected === count;
  return (
    <div className={`import-group${group.selected === 0 ? ' is-paused' : ''}`}>
      <div className="row import-row">
        <input type="checkbox" className="check" checked={group.selected > 0} aria-label={`${group.name} übernehmen`}
          ref={(el) => { if (el) el.indeterminate = group.selected > 0 && !all; }}
          onChange={(e) => onSelect(e.target.checked)} />
        <button type="button" className="grow group-toggle" onClick={onToggle} aria-expanded={open}
          aria-label={`${group.name}: ${count} Umsätze ${open ? 'zuklappen' : 'zeigen'}`}>
          <span className="trunc">
            {group.name}
            {group.source && group.category !== null && <span className="pill pill-inline">{SOURCE_LABEL[group.source]}</span>}
          </span>
          <span className="sub-line trunc">{count === 1 ? '1 Umsatz' : `${count} Umsätze`} · {period(group.first, group.last)}</span>
        </button>
        <span className={`end strong${group.income ? ' pos' : ''}`}>{eur(group.total, { sign: group.income })}</span>
        <div className="import-category">
          <select className="select" value={group.category === 'mixed' ? 'mixed' : group.category ?? ''} disabled={group.selected === 0}
            aria-label={`Kategorie für ${group.name}`}
            onChange={(e) => (e.target.value === 'new' ? onNewCategory() : e.target.value !== 'mixed' && onCategory(e.target.value === '' ? null : Number(e.target.value)))}>
            <option value="">Kategorie wählen</option>
            {group.category === 'mixed' && <option value="mixed">Verschiedene</option>}
            {categoryOptions(categories, group.income).map((c) => <option key={c.id} value={c.id}>{c.label}</option>)}
            <option value="new">+ Neue Kategorie …</option>
          </select>
        </div>
      </div>
      {open && <div className="rows import-group-rows">{children}</div>}
    </div>
  );
}

/** "Rest zuordnen": alle ausgewählten Umsätze ohne Kategorie je Richtung in eine Sammelkategorie */
function RestDialog({ categories, rows, choices, onClose, onApply }: {
  categories: Category[]; rows: ImportRow[]; choices: Record<string, Choice>;
  onClose: () => void; onApply: (expense: number | null, income: number | null) => void;
}) {
  const open = rows.filter((r) => r.status === 'new' && choices[r.key].selected && choices[r.key].category === null);
  const expenses = open.filter((r) => r.amount < 0).length;
  const incomes = open.length - expenses;
  // Vorbelegt mit einer Kategorie namens "Sonstiges"/"Sonstige Einnahmen", falls es sie gibt
  const pick = (income: boolean) => categoryOptions(categories, income).find((c) => /sonstig/i.test(c.label))?.id ?? null;
  const [expense, setExpense] = useState<number | null>(expenses ? pick(false) : null);
  const [income, setIncome] = useState<number | null>(incomes ? pick(true) : null);

  const select = (id: string, label: string, isIncome: boolean, value: number | null, set: (v: number | null) => void) => (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      <select className="select" id={id} value={value ?? ''} onChange={(e) => set(e.target.value === '' ? null : Number(e.target.value))}>
        <option value="">Nicht zuordnen</option>
        {categoryOptions(categories, isIncome).map((c) => <option key={c.id} value={c.id}>{c.label}</option>)}
      </select>
    </div>
  );

  return (
    <Dialog title="Rest zuordnen" onClose={onClose}>
      <p className="muted">
        Alle ausgewählten Umsätze, die noch keine Kategorie haben, bekommen diese Sammelkategorie. Im Haushaltsbuch kannst du
        sie später jederzeit umstellen.
      </p>
      <div className="dialog-form">
        {expenses > 0 && select('rest-expense', `${expenses} Ausgaben`, false, expense, setExpense)}
        {incomes > 0 && select('rest-income', `${incomes} Einnahmen`, true, income, setIncome)}
      </div>
      <div className="dialog-actions">
        <button className="btn" onClick={onClose}>Abbrechen</button>
        <button className="btn btn-primary" onClick={() => onApply(expense, income)} disabled={expense === null && income === null}>Zuordnen</button>
      </div>
    </Dialog>
  );
}

const TYPE_LABEL: Record<string, string> = { income: 'Einkommen', fixed_expense: 'Fixkosten', variable_expense: 'Variable Ausgabe' };

/** Neue Kategorie direkt aus der Vorschau: unter einer Hauptkategorie der passenden Richtung oder als neue Hauptkategorie */
function NewCategoryDialog({ income, categories, onClose, onCreated }: {
  income: boolean; categories: Category[]; onClose: () => void; onCreated: (id: number) => void;
}) {
  const add = useAddCategory();
  const notify = useToast();
  const types: Category['type'][] = income ? ['income'] : ['fixed_expense', 'variable_expense'];
  const mains = categories.filter((c) => c.parent_id === null && types.includes(c.type)).sort((a, b) => a.name.localeCompare(b.name, 'de'));
  const [name, setName] = useState('');
  const [place, setPlace] = useState(mains[0] ? `main:${mains[0].id}` : `type:${types[0]}`);
  const [error, setError] = useState('');

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!name.trim()) {
      setError('Bitte einen Namen eingeben.');
      return;
    }
    const [kind, value] = place.split(':');
    const parent = kind === 'main' ? mains.find((m) => m.id === Number(value)) : undefined;
    add.mutate({ name: name.trim(), type: parent?.type ?? (value as Category['type']), parent_id: parent?.id ?? null }, {
      onSuccess: ({ category_id }) => {
        notify(`${parent ? `${parent.name} · ` : ''}${name.trim()} angelegt`);
        onCreated(category_id);
        onClose();
      },
      onError: (failure) => setError(failure.message),
    });
  };

  return (
    <Dialog title="Neue Kategorie" onClose={onClose} busy={add.isPending}>
      <form className="dialog-form" onSubmit={submit} noValidate>
        <div className="field">
          <label htmlFor="new-category-name">Name</label>
          <input className="input" id="new-category-name" placeholder="z. B. Lebensversicherung" maxLength={60} value={name}
            onChange={(e) => setName(e.target.value)} aria-invalid={error ? true : undefined} />
        </div>
        <div className="field">
          <label htmlFor="new-category-place">Einordnen unter</label>
          <select className="select" id="new-category-place" value={place} onChange={(e) => setPlace(e.target.value)}>
            {/* Bei Ausgaben die Art dazu: "Mobilität" kann es als Fixkosten und als variable Ausgabe geben */}
            {mains.map((m) => <option key={m.id} value={`main:${m.id}`}>{income ? m.name : `${m.name} (${TYPE_LABEL[m.type]})`}</option>)}
            {types.map((t) => <option key={t} value={`type:${t}`}>Als eigene Hauptkategorie ({TYPE_LABEL[t]})</option>)}
          </select>
        </div>
        {error && <p className="err" role="alert">{error}</p>}
        <div className="dialog-actions">
          <button type="button" className="btn" onClick={onClose} disabled={add.isPending}>Abbrechen</button>
          <button type="submit" className="btn btn-primary" disabled={add.isPending}>{add.isPending ? 'Legt an …' : 'Anlegen und zuordnen'}</button>
        </div>
      </form>
    </Dialog>
  );
}

type RowProps = {
  row: ImportRow;
  choice: Choice;
  categories: Parameters<typeof categoryOptions>[0];
  onSelect: (selected: boolean) => void;
  onCategory: (category: number | null) => void;
  onNewCategory: () => void;
};

function PreviewRow({ row, choice, categories, onSelect, onCategory, onNewCategory }: RowProps) {
  const { eur } = useMoney();
  const income = row.amount > 0;
  const name = row.counterparty || row.purpose || 'Umsatz';
  const sub = [dayShort(row.date), row.counterparty && row.purpose].filter(Boolean).join(' · ');
  return (
    <div className={`row import-row${row.status !== 'new' || !choice.selected ? ' is-paused' : ''}`}>
      <input type="checkbox" className="check" checked={row.status === 'new' && choice.selected} disabled={row.status !== 'new'}
        onChange={(e) => onSelect(e.target.checked)} aria-label={`${name} am ${dayShort(row.date)} übernehmen`} />
      <div className="grow">
        <span className="trunc">{name}</span>
        <span className="sub-line trunc">{sub}</span>
      </div>
      <span className={`end strong${income ? ' pos' : ''}`}>{eur(row.amount, { sign: income })}</span>
      <div className="import-category">
        {row.status === 'new'
          ? (
            <select className="select" value={choice.category ?? ''} aria-label={`Kategorie für ${name} am ${dayShort(row.date)}`}
              onChange={(e) => (e.target.value === 'new' ? onNewCategory() : onCategory(e.target.value === '' ? null : Number(e.target.value)))}
              disabled={!choice.selected}>
              <option value="">Kategorie wählen</option>
              {categoryOptions(categories, income).map((c) => <option key={c.id} value={c.id}>{c.label}</option>)}
              <option value="new">+ Neue Kategorie …</option>
            </select>
          )
          : <span className="pill">{row.status === 'covered' ? `schon erfasst: ${row.covered_by?.description ?? 'wiederkehrend'}` : 'schon importiert'}</span>}
      </div>
    </div>
  );
}
