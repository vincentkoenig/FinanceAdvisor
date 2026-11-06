// Vermögensverlauf der Übersicht. Eigene Datei, damit das Diagramm nachgeladen wird und nicht den
// Start der App vergrößert.
import { useWealthHistory } from '../../api/balances';
import { ValueChart } from '../../components/ValueChart';
import { useMoney } from '../../lib/privacy';

export function WealthPanel() {
  const wealth = useWealthHistory();
  const { eur } = useMoney();
  const points = wealth.data ?? [];
  if (points.length < 2) return null;

  return (
    <section className="panel" aria-labelledby="h-wealth">
      <div className="panel-head"><h2 id="h-wealth">Vermögensverlauf</h2></div>
      <div className="chart-slot">
        <ValueChart points={points.map((p) => ({ date: p.date, value: p.total }))} height={220} label="Gesamtvermögen"
          detail={(i) => `Depot ${eur(points[i].depot)} · Cash ${eur(points[i].cash)}`} />
      </div>
    </section>
  );
}
