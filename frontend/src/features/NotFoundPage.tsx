import { Link } from 'react-router';

export function NotFoundPage() {
  return (
    <>
      <div className="title-row"><div className="text"><h1>Seite nicht gefunden</h1></div></div>
      <section className="panel">
        <p className="muted" style={{ marginBottom: 16 }}>Diese Adresse gibt es im neuen FinTrack nicht.</p>
        <Link className="btn" to="/">Zur Übersicht</Link>
      </section>
    </>
  );
}
