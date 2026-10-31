// Signatur der App: wohin das Einkommen eines Monats geht (Übersicht und Haushaltsbuch)
import type { monthFlow } from '../features/home/model';
import { useMoney } from '../lib/privacy';

export function MonthFlow({ flow }: { flow: ReturnType<typeof monthFlow> }) {
  const { eur } = useMoney();
  if (flow.income <= 0 && flow.parts.every((p) => p.value === 0)) {
    return <p className="empty-line">Für diesen Monat gibt es noch keine Buchungen.</p>;
  }
  const share = (value: number) => (flow.income > 0 ? Math.round((value / flow.income) * 100) : 0);
  return (
    <>
      <p className="muted num">Einnahmen <b className="strong">{eur(flow.income)}</b></p>
      {flow.drawable
        ? (
          <div className="flow" role="img" aria-label={flow.parts.map((p) => `${p.label} ${share(p.value)} %`).join(', ')}>
            {flow.parts.filter((p) => p.value > 0).map((p) => (
              <span key={p.key} className={`flow-${p.key}`} style={{ flex: p.value }}>
                {p.value / flow.income > 0.12 ? p.short : ''}
              </span>
            ))}
          </div>
        )
        : <p className="flow-note neg">Die Ausgaben liegen {eur(-flow.left)} über den Einnahmen.</p>}
      <table className="legend-table num">
        <tbody>
          {flow.parts.map((p) => (
            <tr key={p.key}>
              <td><span className={`dot flow-${p.key}`} />{p.label}</td>
              <td className="r">{eur(p.value)}</td>
              <td className="r muted pct-col">{flow.income > 0 ? `${share(p.value)} %` : ''}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  );
}
