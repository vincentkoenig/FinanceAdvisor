// Geteilte Dateien. Frage der Seite: Wohin mit dem, was gerade über "Teilen → FinTrack" (Android) kam?
// Kontoauszug oder Umsatzliste → Haushaltsbuch, Abrechnungen und Exporte vom Broker → Depot. Die Dateien liegen bis dahin
// nur kurz auf dem Gerät (siehe lib/sharedFile.ts); die gewählte Import-Seite holt sie ab und löscht sie dabei.
import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router';
import { Icon } from '../../components/Icon';
import { type SharedInfo, isZipName, peekSharedFiles, takeSharedFiles } from '../../lib/sharedFile';

export function SharedPage() {
  const navigate = useNavigate();
  const [files, setFiles] = useState<SharedInfo[] | null>(null);
  useEffect(() => {
    peekSharedFiles().then(setFiles);
  }, []);

  // Das Haushaltsbuch liest genau eine CSV- oder PDF-Datei
  const bankFits = files?.length === 1 && !isZipName(files[0]);
  const discard = () => takeSharedFiles().then(() => navigate('/', { replace: true }));

  return (
    <>
      <div className="title-row">
        <div className="text">
          <h1>Geteilte Dateien</h1>
          <p className="sub">Wähle, wohin sie gehen. Vor dem Speichern siehst du alles in einer Vorschau.</p>
        </div>
      </div>

      {files === null && <p className="muted" role="status">Lädt …</p>}

      {files?.length === 0 && (
        <section className="panel" aria-labelledby="h-missing">
          <div className="panel-head"><h2 id="h-missing">Nichts angekommen</h2></div>
          <p className="err" role="alert">Die geteilte Datei ist nicht angekommen. Bitte wähle sie auf der Import-Seite von Hand.</p>
          <div className="dialog-actions">
            <Link className="btn" to="/budget/import">Umsätze importieren</Link>
            <Link className="btn" to="/portfolio/import">Abrechnungen importieren</Link>
          </div>
        </section>
      )}

      {files && files.length > 0 && (
        <>
          <section className="panel" aria-labelledby="h-files">
            <div className="panel-head"><h2 id="h-files">{files.length === 1 ? '1 Datei' : `${files.length} Dateien`}</h2></div>
            <ul className="file-results">
              {files.map((f, index) => <li key={`${f.name}-${index}`}><span className="strong trunc">{f.name}</span></li>)}
            </ul>
          </section>

          <section className="panel" aria-labelledby="h-target">
            <div className="panel-head"><h2 id="h-target">Importieren nach</h2></div>
            <div className="rows">
              <button className="row row-btn" disabled={!bankFits} onClick={() => navigate('/budget/import?shared=1', { replace: true })}>
                <Icon name="wallet" size={20} />
                <div className="grow">
                  <span className="trunc">Haushaltsbuch</span>
                  <span className="sub-line">
                    {bankFits ? 'Kontoauszug als PDF oder Umsatzliste (CSV) deiner Bank' : 'Nimmt genau eine CSV- oder PDF-Datei'}
                  </span>
                </div>
                <Icon name="right" size={16} />
              </button>
              <button className="row row-btn" onClick={() => navigate('/portfolio/import?shared=1', { replace: true })}>
                <Icon name="chart" size={20} />
                <div className="grow">
                  <span className="trunc">Depot</span>
                  <span className="sub-line">Abrechnungen vom Broker (PDF, auch als ZIP), Trade-Republic-Export oder Krypto-CSV</span>
                </div>
                <Icon name="right" size={16} />
              </button>
            </div>
            <div className="dialog-actions">
              <button className="btn" onClick={discard}>Verwerfen</button>
            </div>
          </section>
        </>
      )}
    </>
  );
}
