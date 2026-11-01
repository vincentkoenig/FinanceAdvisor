// Abrechnungen importieren. Frage der Seite: Welche Käufe und Verkäufe sollen ins Depot?
// Dateien wählen (auch mehrere): PDF-Abrechnungen von Brokern (persönliche Angaben werden entfernt, dann
// liest die KI die Ausführungen aus) und CSV-Exporte von Krypto-Apps wie Bison (ohne KI, Spalten notfalls
// von Hand zuordnen) → Vorschau prüfen → buchen. Gespeichert wird erst beim Buchen, die Dateien nirgends.
import { useState } from 'react';
import { Link, useNavigate } from 'react-router';
import {
  type CryptoField, type CryptoMapping, type DepotRow, UnknownColumnsError, previewCryptoImport, previewDepotImport, useCommitDepotImport,
} from '../../api/imports';
import { Icon } from '../../components/Icon';
import { useToast } from '../../components/Toast';
import { dayShort, qty } from '../../lib/format';
import { useMoney } from '../../lib/privacy';

type FileResult =
  | { kind: 'rows'; name: string; rows: DepotRow[]; info: string; sent?: string }
  | { kind: 'error'; name: string; error: string }
  | { kind: 'mapping'; name: string; file: File; columns: string[]; error: string };

const STATUS_TEXT: Record<Exclude<DepotRow['status'], 'new'>, string> = {
  duplicate: 'schon gebucht',
  unknown: 'Wertpapier nicht gefunden',
  insufficient: 'zu wenig Stück im Depot',
};

const CRYPTO_FIELDS: { field: CryptoField; label: string }[] = [
  { field: 'date', label: 'Datum' },
  { field: 'type', label: 'Art (Kauf/Verkauf)' },
  { field: 'asset', label: 'Kryptowährung' },
  { field: 'quantity', label: 'Menge' },
  { field: 'price', label: 'Kurs in Euro' },
  { field: 'total', label: 'Betrag in Euro' },
  { field: 'fee', label: 'Gebühr' },
];

const isCsv = (file: File) => /\.csv$/i.test(file.name) || file.type === 'text/csv';
const count = (n: number) => `${n} Ausführung${n === 1 ? '' : 'en'}`;

export function DepotImportPage() {
  const commit = useCommitDepotImport();
  const notify = useToast();
  const navigate = useNavigate();
  const { eur } = useMoney();
  const [files, setFiles] = useState<FileResult[]>([]);
  const [reading, setReading] = useState<string | null>(null);
  const [selected, setSelected] = useState<Record<string, boolean>>({});
  const [mapping, setMapping] = useState<CryptoMapping>({});
  const [inputKey, setInputKey] = useState(0);
  const [error, setError] = useState<string | null>(null);

  const read = async (file: File, withMapping?: CryptoMapping): Promise<FileResult> => {
    try {
      if (isCsv(file)) {
        const result = await previewCryptoImport(file, withMapping);
        const skipped = result.skipped.length ? ` · ${result.skipped.length} übersprungen (z. B. Ein- und Auszahlungen)` : '';
        return { kind: 'rows', name: file.name, rows: result.rows, info: count(result.rows.length) + skipped };
      }
      const result = await previewDepotImport(file);
      const info = result.is_trade_statement ? count(result.rows.length) : 'keine Kauf- oder Verkaufsabrechnung';
      return { kind: 'rows', name: file.name, rows: result.rows, info: info + (result.note ? ` · ${result.note}` : ''), sent: result.sent_text };
    } catch (failure) {
      if (failure instanceof UnknownColumnsError && failure.columns.length) {
        return { kind: 'mapping', name: file.name, file, columns: failure.columns, error: failure.message };
      }
      return { kind: 'error', name: file.name, error: (failure as Error).message };
    }
  };

  const remember = (result: FileResult) => {
    if (result.kind === 'rows') setSelected((current) => ({ ...current, ...Object.fromEntries(result.rows.map((r) => [r.key, r.status === 'new'])) }));
  };

  // Nacheinander, damit die Reihenfolge stimmt und der Server nicht mit vielen Auswertungen auf einmal belastet wird
  const pick = async (list: FileList | null) => {
    if (!list?.length) return;
    setError(null);
    for (const file of Array.from(list)) {
      setReading(file.name);
      const result = await read(file);
      remember(result);
      setFiles((current) => [...current, result]);
    }
    setReading(null);
    setInputKey((k) => k + 1);
  };

  const applyMapping = async (index: number, file: File) => {
    setReading(file.name);
    const result = await read(file, mapping);
    remember(result);
    setFiles((current) => current.map((f, i) => (i === index ? result : f)));
    setReading(null);
  };

  const rows = files.flatMap((f) => (f.kind === 'rows' ? f.rows : []));
  // Dieselbe Ausführung aus zwei Dateien nur einmal
  const unique = rows.filter((row, index) => rows.findIndex((r) => r.key === row.key) === index);
  const chosen = unique.filter((r) => r.status === 'new' && selected[r.key]);

  const save = () => commit.mutate(
    chosen.map((r) => ({ type: r.type, symbol: r.symbol!, name: r.asset_name ?? r.name, date: r.date, quantity: r.quantity, price: r.price! })),
    {
      onSuccess: (result) => {
        notify(result.skipped ? `${result.message}, ${result.skipped} waren schon da` : result.message);
        navigate('/portfolio');
      },
      onError: (failure) => setError(failure.message),
    },
  );

  const reset = () => {
    setFiles([]);
    setSelected({});
    setMapping({});
    setError(null);
  };

  return (
    <>
      <div className="title-row">
        <div className="text">
          <h1>Abrechnungen importieren</h1>
          <p className="sub">PDF-Abrechnungen deiner Broker (z. B. Trade Republic, HypoVereinsbank) und CSV-Exporte von Krypto-Apps wie Bison.</p>
        </div>
        <div className="actions">
          <Link to="/portfolio" className="btn"><Icon name="left" size={16} />Portfolio</Link>
        </div>
      </div>

      <section className="panel" aria-labelledby="h-pdf">
        <div className="panel-head"><h2 id="h-pdf">Dateien</h2></div>
        <div className="file-row">
          <label className="btn btn-primary" htmlFor="depot-files"><Icon name="upload" size={16} />Dateien wählen</label>
          <input key={inputKey} className="sr-only" type="file" id="depot-files" accept="application/pdf,.pdf,.csv,text/csv" multiple
            onChange={(e) => pick(e.target.files)} disabled={reading !== null || commit.isPending} />
          <span className="muted trunc" role="status">{reading ? `Liest ${reading} …` : files.length ? `${files.length} gelesen` : 'Mehrere Dateien auf einmal gehen'}</span>
        </div>
        <p className="hint">
          PDFs: Vor dem Auswerten entfernt FinTrack Name, Adresse, IBAN sowie Kunden- und Depotnummern. Nur der Rest (Wertpapier,
          ISIN, Datum, Stück, Kurs, Gebühren) geht zum Auslesen an OpenAI. CSV-Dateien liest FinTrack selbst, ohne KI.
          Keine Datei wird gespeichert.
        </p>
        {files.length > 0 && (
          <ul className="file-results">
            {files.map((f, index) => (
              <li key={`${f.name}-${index}`}>
                <span className="strong trunc">{f.name}</span>
                {f.kind === 'error' && <span className="err">{f.error}</span>}
                {f.kind === 'rows' && (
                  <>
                    <span className="muted">{f.info}</span>
                    {f.sent !== undefined && (
                      <details>
                        <summary>Gesendeter Text</summary>
                        <pre className="sent-text">{f.sent}</pre>
                      </details>
                    )}
                  </>
                )}
                {f.kind === 'mapping' && (
                  <div className="file-mapping">
                    <p className="muted">{f.error} Für den Preis reicht Kurs oder Betrag.</p>
                    <div className="form-grid">
                      {CRYPTO_FIELDS.map(({ field, label }) => (
                        <div className="field" key={field}>
                          <label htmlFor={`crypto-${index}-${field}`}>{label}</label>
                          <select className="select" id={`crypto-${index}-${field}`} value={mapping[field] ?? ''}
                            onChange={(e) => setMapping((m) => {
                              const next = { ...m };
                              if (e.target.value === '') delete next[field]; else next[field] = Number(e.target.value);
                              return next;
                            })}>
                            <option value="">nicht vorhanden</option>
                            {f.columns.map((name, column) => <option key={column} value={column}>{name || `Spalte ${column + 1}`}</option>)}
                          </select>
                        </div>
                      ))}
                    </div>
                    <div className="dialog-actions">
                      <button className="btn btn-primary" onClick={() => applyMapping(index, f.file)} disabled={reading !== null}>Vorschau laden</button>
                    </div>
                  </div>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>

      {unique.length > 0 && (
        <section className="panel" aria-labelledby="h-trades">
          <div className="panel-head">
            <h2 id="h-trades">Vorschau</h2>
            <span className="meta">{chosen.length} von {unique.length} ausgewählt</span>
          </div>
          <div className="rows">
            {unique.map((r) => {
              const label = `${r.type === 'buy' ? 'Kauf' : 'Verkauf'} ${r.asset_name ?? r.name} am ${dayShort(r.date)}`;
              return (
                <div className={`row import-row${r.status !== 'new' || !selected[r.key] ? ' is-paused' : ''}`} key={r.key}>
                  <input type="checkbox" className="check" checked={r.status === 'new' && Boolean(selected[r.key])} disabled={r.status !== 'new'}
                    onChange={(e) => setSelected((s) => ({ ...s, [r.key]: e.target.checked }))} aria-label={`${label} buchen`} />
                  <div className="grow">
                    <span className="trunc">
                      <span className={`pill pill-inline-start${r.type === 'sell' ? ' pill-warn' : ''}`}>{r.type === 'buy' ? 'Kauf' : 'Verkauf'}</span>
                      {r.asset_name ?? r.name}
                    </span>
                    <span className="sub-line trunc">
                      {[dayShort(r.date), r.symbol ?? r.isin, `${qty(r.quantity)} × ${eur(r.quote)}`, r.fees ? `${eur(r.fees)} Gebühren` : null].filter(Boolean).join(' · ')}
                    </span>
                  </div>
                  <span className="end strong">{r.price !== null ? eur(r.price * r.quantity) : '–'}</span>
                  {r.status !== 'new' && <span className="pill">{STATUS_TEXT[r.status]}</span>}
                </div>
              );
            })}
          </div>
          {error && <p className="err" role="alert">{error}</p>}
          <div className="dialog-actions">
            <button className="btn" onClick={reset} disabled={commit.isPending}>Verwerfen</button>
            <button className="btn btn-primary" onClick={save} disabled={commit.isPending || chosen.length === 0}>
              {commit.isPending ? 'Bucht …' : chosen.length === 1 ? '1 Ausführung buchen' : `${chosen.length} Ausführungen buchen`}
            </button>
          </div>
        </section>
      )}
    </>
  );
}
