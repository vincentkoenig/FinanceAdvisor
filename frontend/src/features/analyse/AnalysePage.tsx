// Portfolio-Analyse durch den KI-Berater. Frage der Seite: Wie steht mein Depot da?
// Oben die neueste Analyse mit Einschätzung, Risiko und Empfehlungen, daneben die Streuung
// (im Backend aus der Verteilung berechnet, nicht vom Modell geschätzt), darunter frühere Analysen.
import { useAnalyses, useRunAnalysis } from '../../api/advisor';
import { usePositions } from '../../api/overview';
import { Loaded } from '../../components/Loaded';
import { useToast } from '../../components/Toast';
import { eur } from '../../lib/format';

const scoreText = (score: number | null) => (score === null ? '–' : `${score} von 10`);

export function AnalysePage() {
  const analyses = useAnalyses();
  const positions = usePositions();
  const run = useRunAnalysis();
  const notify = useToast();
  const [latest, ...older] = analyses.data ?? [];
  const noPositions = positions.data?.length === 0;

  const start = () => run.mutate(undefined, {
    onSuccess: () => notify('Neue Analyse erstellt'),
    onError: (error) => notify(error.message, { error: true }),
  });

  return (
    <>
      <div className="title-row">
        <div className="text">
          <h1>Analyse</h1>
          <p className="sub">
            {latest
              ? <>Zuletzt am {latest.created_at.slice(0, 10)} · Streuung {scoreText(latest.diversification_score)}</>
              : analyses.isSuccess && 'Der KI-Berater schätzt dein Depot ein: Risiko, Streuung und worauf du achten kannst'}
          </p>
        </div>
        <div className="actions">
          <button className="btn btn-primary" onClick={start} disabled={run.isPending || noPositions}>
            {run.isPending ? 'Analysiert …' : 'Neue Analyse'}
          </button>
        </div>
      </div>

      {run.isPending && <p className="muted" role="status">Die Analyse dauert meist 10 bis 20 Sekunden.</p>}

      <Loaded queries={[analyses]}>
        {() => !latest
          ? (
            <section className="panel">
              <p className="empty-line">
                {noPositions
                  ? 'Für eine Analyse braucht dein Depot mindestens eine Position.'
                  : 'Noch keine Analyse. Mit „Neue Analyse“ schätzt der KI-Berater dein Depot ein.'}
              </p>
            </section>
          )
          : (
            <>
              <div className="grid grid-3">
                <section className="panel span-2" aria-labelledby="h-summary">
                  <div className="panel-head"><h2 id="h-summary">Einschätzung</h2><span className="meta">{latest.created_at}</span></div>
                  <p className="prose">{latest.summary}</p>
                  <h3 className="sub-head">Risiko</h3>
                  <p className="prose">{latest.risk_assessment}</p>
                  {latest.recommendations.length > 0 && (
                    <>
                      <h3 className="sub-head">Worauf du achten kannst</h3>
                      <ol className="recommendations">{latest.recommendations.map((r, i) => <li key={i}>{r}</li>)}</ol>
                    </>
                  )}
                  <p className="hint disclaimer">Die Einschätzung stammt von einer KI und ist keine Anlageberatung.</p>
                </section>
                <section className="panel" aria-labelledby="h-score">
                  <h2 id="h-score" className="kpi-label">Streuung</h2>
                  <div className="kpi-value">
                    {latest.diversification_score ?? '–'} <span className="muted kpi-unit">von 10</span>
                  </div>
                  {latest.diversification_score !== null && (
                    <>
                      <div className="score-bar" role="img" aria-label={`Streuung ${latest.diversification_score} von 10`}>
                        <span style={{ width: `${latest.diversification_score * 10}%` }} />
                      </div>
                      <div className="flow-scale"><span>1 gebündelt</span><span>10 breit</span></div>
                    </>
                  )}
                  <p className="hint score-hint">
                    Berechnet aus der Verteilung deines Depots: je gleichmäßiger der Wert auf viele Positionen verteilt ist, desto höher.
                  </p>
                  <div className="kpi-label score-gap">Depotwert bei der Analyse</div>
                  <div className="kpi-value kpi-small">{eur(latest.total_value)}</div>
                </section>
              </div>

              {older.length > 0 && (
                <section className="panel" aria-labelledby="h-older">
                  <div className="panel-head"><h2 id="h-older">Frühere Analysen</h2><span className="meta">{older.length}</span></div>
                  <div className="rows">
                    {older.map((a) => (
                      <details className="row older" key={a.id}>
                        <summary>
                          <span className="grow">
                            <span className="strong">{a.created_at}</span>
                            <span className="sub-line clamp-2">{a.summary}</span>
                          </span>
                          <span className="end">
                            <span className="pill">Streuung {scoreText(a.diversification_score)}</span>
                            <span className="sub-line">{eur(a.total_value, { digits: 0 })}</span>
                          </span>
                        </summary>
                        <div className="older-body">
                          <p className="prose">{a.summary}</p>
                          <h3 className="sub-head">Risiko</h3>
                          <p className="prose">{a.risk_assessment}</p>
                          {a.recommendations.length > 0 && <ol className="recommendations">{a.recommendations.map((r, i) => <li key={i}>{r}</li>)}</ol>}
                        </div>
                      </details>
                    ))}
                  </div>
                </section>
              )}
            </>
          )}
      </Loaded>
    </>
  );
}
