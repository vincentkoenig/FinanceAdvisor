// Sparziele auf der Übersicht: nur der Fortschritt, verwaltet wird im Haushaltsbuch. Eigene Datei, damit
// sie nachgeladen wird und nicht den Start der App vergrößert. Ohne Sparziele erscheint nichts.
import { Link } from 'react-router';
import { useGoals } from '../../api/goals';
import { Fold } from '../../components/Fold';
import { useMoney } from '../../lib/privacy';
import { GoalBars } from '../budget/Goals';

export function GoalsPanel() {
  const goals = useGoals();
  const { eur } = useMoney();
  if (!goals.data || goals.data.goals.length === 0) return null;

  return (
    <Fold id="h-goals" title="Sparziele" peek={eur(goals.data.total)}
      action={<Link to="/budget#goals" className="btn btn-text btn-sm">Verwalten</Link>}>
      <GoalBars goals={goals.data.goals} />
    </Fold>
  );
}
