// Regeln für den Kontoimport: "steht X im Empfänger oder Verwendungszweck, dann Kategorie Y".
// Liste mit Suche, neue anlegen, einzelne löschen. Bekannte Händler (Tankstellen, Supermärkte, ...)
// kennt FinTrack von selbst und stehen hier nicht.
import { useState, type FormEvent } from 'react';
import { useCategories } from '../../api/budget';
import { useAddRule, useDeleteRule, useRules } from '../../api/rules';
import { Icon } from '../../components/Icon';
import { useToast } from '../../components/Toast';
import { categoryOptions } from '../budget/importModel';

export function RulesSection() {
  const rules = useRules();
  const categories = useCategories();
  const add = useAddRule();
  const remove = useDeleteRule();
  const notify = useToast();
  const [search, setSearch] = useState('');
  const [pattern, setPattern] = useState('');
  const [income, setIncome] = useState(false);
  const [category, setCategory] = useState('');
  const [error, setError] = useState('');

  const term = search.trim().toLowerCase();
  const shown = (rules.data ?? []).filter((r) => !term || r.pattern.includes(term) || (r.category_label ?? '').toLowerCase().includes(term));

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (pattern.trim().length < 2 || !category) {
      setError('Bitte ein Wort (mindestens zwei Zeichen) und eine Kategorie angeben.');
      return;
    }
    setError('');
    add.mutate({ pattern: pattern.trim(), income, category_id: Number(category) }, {
      onSuccess: () => { notify(`Regel „${pattern.trim().toLowerCase()}“ gespeichert`); setPattern(''); },
      onError: (failure) => setError(failure.message),
    });
  };

  return (
    <>
      <p className="hint">
        Steht das Wort im Empfänger oder Verwendungszweck, schlägt der Import diese Kategorie vor. Tankstellen, Supermärkte,
        Drogerien und ähnliche bekannte Händler erkennt FinTrack von selbst.
      </p>
      {(rules.data?.length ?? 0) > 5 && (
        <div className="field">
          <label htmlFor="rule-search">Suchen</label>
          <input className="input" id="rule-search" placeholder="Wort oder Kategorie" value={search} onChange={(e) => setSearch(e.target.value)} />
        </div>
      )}
      {rules.isSuccess && rules.data.length === 0 && <p className="empty-line">Noch keine eigenen Regeln.</p>}
      {shown.length > 0 && (
        <ul className="category-list rule-list">
          {shown.map((rule) => (
            <li className="category-item" key={rule.id}>
              <span className="trunc">
                <span className="strong">{rule.pattern}</span>
                <span className="muted"> → {rule.category_label ?? 'Kategorie fehlt'}{rule.income ? ' (Einnahme)' : ''}</span>
              </span>
              <button className="icon-btn" onClick={() => remove.mutate(rule.id, { onSuccess: () => notify(`Regel „${rule.pattern}“ gelöscht`) })}
                aria-label={`Regel ${rule.pattern} löschen`} title="Löschen" disabled={remove.isPending}>
                <Icon name="trash" size={16} />
              </button>
            </li>
          ))}
        </ul>
      )}

      <form className="form-grid" onSubmit={submit} noValidate>
        <div className="field">
          <label htmlFor="rule-pattern">Wenn das Wort vorkommt</label>
          <input className="input" id="rule-pattern" placeholder="z. B. vodafone" maxLength={100} value={pattern}
            onChange={(e) => setPattern(e.target.value)} aria-invalid={error ? true : undefined} />
        </div>
        <div className="field">
          <label htmlFor="rule-category">dann Kategorie</label>
          <select className="select" id="rule-category" value={category} onChange={(e) => setCategory(e.target.value)}>
            <option value="">Kategorie wählen</option>
            {categoryOptions(categories.data ?? [], income).map((c) => <option key={c.id} value={c.id}>{c.label}</option>)}
          </select>
        </div>
        <div className="segmented full" role="group" aria-label="Richtung der Regel">
          <button type="button" aria-pressed={!income} onClick={() => { setIncome(false); setCategory(''); }}>Ausgaben</button>
          <button type="button" aria-pressed={income} onClick={() => { setIncome(true); setCategory(''); }}>Einnahmen</button>
        </div>
        {error && <p className="err full" role="alert">{error}</p>}
        <div className="full form-actions">
          <button className="btn btn-primary" type="submit" disabled={add.isPending}><Icon name="plus" size={16} />Regel speichern</button>
        </div>
      </form>
    </>
  );
}
