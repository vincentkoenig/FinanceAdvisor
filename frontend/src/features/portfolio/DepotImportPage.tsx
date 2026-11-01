// Abrechnungen importieren. Frage der Seite: Welche Käufe und Verkäufe aus den PDFs sollen ins Depot?
// PDFs wählen (auch mehrere) → je Datei werden persönliche Angaben entfernt und die Ausführungen
// ausgelesen → Vorschau prüfen → buchen. Gespeichert wird erst beim Buchen, die PDFs nirgends.
import { useState } from 'react';
import { Link, useNavigate } from 'react-router';
import { type DepotRow, previewDepotImport, useCommitDepotImport } from '../../api/imports';
import { Icon } from '../../components/Icon';
import { useToast } from '../../components/Toast';
import { dayShort, qty } from '../../lib/format';
import { useMoney } from '../../lib/privacy';

type FileResult = { name: string; rows: DepotRow[]; note: string | null; isStatement: boolean; sent: string } | { name: string; error: string };

const STATUS_TEXT: Record<Exclude<DepotRow['status'], 'new'>, string> = {
  duplicate: 'schon gebucht',
  unknown: 'Wertpapier nicht gefunden',
  insufficient: 'zu wenig Stück im Depot',
};

export function DepotImportPage() {
  const commit = useCommitDepotImport();
  const notify = useToast();
  const navigate = useNavigate();
  const { eur } = useMoney();
  const [files, setFiles] = useState<FileResult[]>([]);
  const [reading, setReading] = useState<string | null>(null);
  const [selected, setSelected] = useState<Record<string, boolean>>({});
  const [inputKey, setInputKey] = useState(0);
  const [error, setError] = useState<string | null>(null);

  // Nacheinander, damit die Reihenfolge stimmt und der Server nicht mit vielen Auswertungen auf einmal belastet wird
  const pick = async (list: FileList | null) => {
    if (!list?.length) return;
    setError(null);
    for (const file of Array.from(list)) {
      setReading(file.name);
      try {
        const result = await previewDepotImport(file);
        setFiles((current) => [...current, { name: file.name, rows: result.rows, note: result.note, isStatement: result.is_trade_statement, sent: result.sent_text }]);
        setSelected((current) => ({ ...current, ...Object.fromEntries(result.rows.map((r) => [r.key, r.status === 'new'])) }));
      } catch (failure) {
        setFiles((current) => [...current, { name: file.name, error: (failure as Error).message }]);
      }
    }
    setReading(null);
    setInputKey((k) => k + 1);
  };

  const rows = files.flatMap((f) => ('rows' in f ? f.rows : []));
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

  return (
    <>
      <div className="title-row">
        <div className="text">
          <h1>Abrechnungen importieren</h1>
          <p className="sub">PDF-Abrechnungen deiner Broker, zum Beispiel Trade Republic oder HypoVereinsbank.</p>
        </div>
        <div className="actions">
          <Link to="/portfolio" className="btn"><Icon name="left" size={16} />Portfolio</Link>
        </div>
      </div>

      <section className="panel" aria-labelledby="h-pdf">
        <div className="panel-head"><h2 id="h-pdf">Dateien</h2></div>
        <div className="file-row">
          <label className="btn btn-primary" htmlFor="depot-files"><Icon name="upload" size={16} />PDFs wählen</label>
          <input key={inputKey} className="sr-only" type="file" id="depot-files" accept="application/pdf,.pdf" multiple
            onChange={(e) => pick(e.target.files)} disabled={reading !== null || commit.isPending} />
          <span className="muted trunc" role="status">{reading ? `Liest ${reading} …` : files.length ? `${files.length} gelesen` : 'Mehrere Dateien auf einmal gehen'}</span>
        </div>
        <p className="hint">
          Vor dem Auswerten entfernt FinTrack Name, Adresse, IBAN sowie Kunden- und Depotnummern. Nur der Rest (Wertpapier, ISIN,
          Datum, Stück, Kurs, Gebühren) geht zum Auslesen an OpenAI. Die PDFs werden nicht gespeichert.
        </p>
        {files.length > 0 && (
          <ul className="file-results">
            {files.map((f, index) => (
              <li key={`${f.name}-${index}`}>
                <span className="strong trunc">{f.name}</span>
                {'error' in f
                  ? <span className="err">{f.error}</span>
                  : (
                    <>
                      <span className="muted">{f.isStatement ? `${f.rows.length} Ausführung${f.rows.length === 1 ? '' : 'en'}` : 'keine Kauf- oder Verkaufsabrechnung'}{f.note ? ` · ${f.note}` : ''}</span>
                      <details>
                        <summary>Gesendeter Text</summary>
                        <pre className="sent-text">{f.sent}</pre>
                      </details>
                    </>
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
            <button className="btn" onClick={() => { setFiles([]); setSelected({}); setError(null); }} disabled={commit.isPending}>Verwerfen</button>
            <button className="btn btn-primary" onClick={save} disabled={commit.isPending || chosen.length === 0}>
              {commit.isPending ? 'Bucht …' : chosen.length === 1 ? '1 Ausführung buchen' : `${chosen.length} Ausführungen buchen`}
            </button>
          </div>
        </section>
      )}
    </>
  );
}
