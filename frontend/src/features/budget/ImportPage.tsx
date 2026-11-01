// Umsätze importieren. Frage der Seite: Welche Umsätze aus dem Bankexport sollen ins Haushaltsbuch?
// Datei wählen → (Spalten zuordnen, falls nicht erkannt) → Vorschau prüfen, Kategorien setzen → übernehmen.
// Gespeichert wird erst beim Übernehmen; die Datei selbst bleibt nirgends liegen.
import { useState } from 'react';
import { Link, useNavigate } from 'react-router';
import { useCategories } from '../../api/budget';
import { type ColumnMapping, type ImportPreview, type ImportRow, UnknownColumnsError, useCommitBankImport, usePreviewBankImport } from '../../api/imports';
import { Icon } from '../../components/Icon';
import { useToast } from '../../components/Toast';
import { dayShort } from '../../lib/format';
import { useMoney } from '../../lib/privacy';
import { MAPPING_FIELDS, type Choice, assignCategory, categoryOptions, initialChoices, toCommit } from './importModel';

export function ImportPage() {
  const previewImport = usePreviewBankImport();
  const commit = useCommitBankImport();
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
    setColumns(null);
    setError(null);
    setInputKey((k) => k + 1);
  };

  const summary = preview ? toCommit(preview.rows, choices) : null;
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
          <label className="btn btn-primary" htmlFor="bank-file"><Icon name="upload" size={16} />{file ? 'Andere Datei' : 'CSV-Datei wählen'}</label>
          <input key={inputKey} className="sr-only" type="file" id="bank-file" accept=".csv,text/csv,text/plain"
            onChange={(e) => pick(e.target.files?.[0])} disabled={previewImport.isPending || commit.isPending} />
          <span className="muted trunc">{previewImport.isPending ? 'Liest …' : file?.name ?? 'Im Online-Banking: Umsätze → Export → CSV'}</span>
        </div>
        <p className="hint">Die Datei wird nur gelesen und nicht gespeichert. Umsätze, die schon im Haushaltsbuch stehen, werden erkannt.</p>
        {error && !columns && <p className="err" role="alert">{error}</p>}
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
          <div className="rows">
            {preview.rows.map((row) => (
              <PreviewRow key={row.key} row={row} choice={choices[row.key]} categories={categories.data ?? []}
                onSelect={(selected) => setChoices((c) => ({ ...c, [row.key]: { ...c[row.key], selected } }))}
                onCategory={(category) => setChoices((c) => assignCategory(preview.rows, c, row.key, category))} />
            ))}
          </div>
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
    </>
  );
}

type RowProps = {
  row: ImportRow;
  choice: Choice;
  categories: Parameters<typeof categoryOptions>[0];
  onSelect: (selected: boolean) => void;
  onCategory: (category: number | null) => void;
};

function PreviewRow({ row, choice, categories, onSelect, onCategory }: RowProps) {
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
              onChange={(e) => onCategory(e.target.value === '' ? null : Number(e.target.value))} disabled={!choice.selected}>
              <option value="">Kategorie wählen</option>
              {categoryOptions(categories, income).map((c) => <option key={c.id} value={c.id}>{c.label}</option>)}
            </select>
          )
          : <span className="pill">{row.status === 'covered' ? `schon erfasst: ${row.covered_by?.description ?? 'wiederkehrend'}` : 'schon importiert'}</span>}
      </div>
    </div>
  );
}
