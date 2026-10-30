// Übersicht: in diesem ersten Schritt nur der Rahmen. Die Inhalte (Gesamtvermögen, Zu tun,
// Monatsfluss) kommen mit dem nächsten PR; bis dahin führt ein Link zur bisherigen Ansicht.
import { useMe } from '../../api/auth';

export function HomePage() {
  const { data: user } = useMe();
  return (
    <>
      <div className="title-row">
        <div className="text">
          <h1>Übersicht</h1>
          <p className="sub">Angemeldet als {user?.email}</p>
        </div>
      </div>
      <section className="panel hero" aria-labelledby="h-new">
        <h2 id="h-new" className="lead-label">Neues FinTrack</h2>
        <p className="lead-figure">Im Aufbau</p>
        <p className="lead-sub">
          Die neue Oberfläche entsteht Seite für Seite. Bis ein Bereich umgezogen ist, öffnen die Links
          oben die bisherige Ansicht, deine Daten sind in beiden dieselben.
        </p>
        <p style={{ marginTop: 16 }}>
          <a className="btn" href="/home-page">Bisherige Übersicht öffnen</a>
        </p>
      </section>
    </>
  );
}
