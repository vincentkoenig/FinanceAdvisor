// Kategorien des Haushaltsbuchs verwalten: je Art (Einnahmen, Fixkosten, variable Ausgaben) die
// Hauptkategorien mit ihren Unterkategorien, neue anlegen, umbenennen oder verschieben und leere löschen.
import { useState, type FormEvent } from 'react';
import { type Category, useAddCategory, useCategories, useDeleteCategory, useUpdateCategory } from '../../api/budget';
import type { CategoryType } from '../../api/overview';
import { Dialog } from '../../components/Dialog';
import { Icon } from '../../components/Icon';
import { useToast } from '../../components/Toast';

const TYPES: { type: CategoryType; label: string }[] = [
  { type: 'income', label: 'Einnahmen' },
  { type: 'fixed_expense', label: 'Fixkosten' },
  { type: 'variable_expense', label: 'Variable Ausgaben' },
];

const byName = (a: Category, b: Category) => a.name.localeCompare(b.name, 'de');

export function CategoriesSection() {
  const categories = useCategories();
  const add = useAddCategory();
  const notify = useToast();
  const [type, setType] = useState<CategoryType>('fixed_expense');
  const [name, setName] = useState('');
  const [parent, setParent] = useState('');
  const [error, setError] = useState('');
  const [removing, setRemoving] = useState<Category | null>(null);
  const [editing, setEditing] = useState<Category | null>(null);

  const all = categories.data ?? [];
  const mains = all.filter((c) => c.type === type && c.parent_id === null).sort(byName);
  const subsOf = (main: Category) => all.filter((c) => c.parent_id === main.id).sort(byName);

  const chooseType = (next: CategoryType) => {
    setType(next);
    setParent('');
    setError('');
  };

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!name.trim()) {
      setError('Bitte einen Namen eingeben.');
      return;
    }
    setError('');
    const parentId = parent ? Number(parent) : null;
    add.mutate({ name: name.trim(), type, parent_id: parentId }, {
      onSuccess: () => {
        const main = mains.find((m) => m.id === parentId);
        notify(main ? `${main.name} · ${name.trim()} angelegt` : `${name.trim()} angelegt`);
        setName('');
      },
      onError: (failure) => setError(failure.message),
    });
  };

  return (
    <>
      <div className="segmented" role="group" aria-label="Art der Kategorien">
        {TYPES.map((t) => (
          <button type="button" key={t.type} aria-pressed={type === t.type} onClick={() => chooseType(t.type)}>{t.label}</button>
        ))}
      </div>

      {categories.isSuccess && mains.length === 0 && <p className="empty-line">Noch keine Kategorien dieser Art.</p>}
      <ul className="category-list">
        {mains.map((main) => (
          <li key={main.id}>
            <div className="category-item strong">
              <span className="trunc">{main.name}</span>
              <button className="icon-btn" onClick={() => setEditing(main)} aria-label={`${main.name} bearbeiten`} title="Bearbeiten">
                <Icon name="edit" size={16} />
              </button>
              <button className="icon-btn" onClick={() => setRemoving(main)} aria-label={`${main.name} löschen`} title="Löschen">
                <Icon name="trash" size={16} />
              </button>
            </div>
            {subsOf(main).length > 0 && (
              <ul>
                {subsOf(main).map((sub) => (
                  <li className="category-item" key={sub.id}>
                    <span className="trunc">{sub.name}</span>
                    <button className="icon-btn" onClick={() => setEditing(sub)} aria-label={`${main.name} · ${sub.name} bearbeiten`} title="Bearbeiten">
                      <Icon name="edit" size={16} />
                    </button>
                    <button className="icon-btn" onClick={() => setRemoving(sub)} aria-label={`${main.name} · ${sub.name} löschen`} title="Löschen">
                      <Icon name="trash" size={16} />
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </li>
        ))}
      </ul>

      <form className="form-grid" onSubmit={submit} noValidate>
        <div className="field">
          <label htmlFor="category-name">Neue Kategorie</label>
          <input className="input" id="category-name" placeholder="z. B. Lebensversicherung" maxLength={60} value={name}
            onChange={(e) => setName(e.target.value)} aria-invalid={error ? true : undefined}
            aria-describedby={error ? 'category-error' : undefined} />
        </div>
        <div className="field">
          <label htmlFor="category-parent">Einordnen unter</label>
          <select className="select" id="category-parent" value={parent} onChange={(e) => setParent(e.target.value)}>
            <option value="">Als eigene Hauptkategorie</option>
            {mains.map((m) => <option key={m.id} value={m.id}>{m.name}</option>)}
          </select>
        </div>
        {error && <p className="err full" id="category-error" role="alert">{error}</p>}
        <div className="full form-actions">
          <button className="btn btn-primary" type="submit" disabled={add.isPending}>
            <Icon name="plus" size={16} />{add.isPending ? 'Legt an …' : 'Anlegen'}
          </button>
        </div>
      </form>

      {editing && <EditCategoryDialog category={editing} categories={all} onClose={() => setEditing(null)} />}
      {removing && <DeleteCategoryDialog category={removing} subs={subsOf(removing)} onClose={() => setRemoving(null)} />}
    </>
  );
}

const TYPE_LABEL: Record<CategoryType, string> = { income: 'Einkommen', fixed_expense: 'Fixkosten', variable_expense: 'Variable Ausgabe' };

/**
 * Umbenennen und verschieben. Einnahmen bleiben bei Einnahmen, Ausgaben bei Ausgaben (zwischen Fix- und
 * variablen Kosten geht es). Eine Hauptkategorie mit Unterkategorien lässt sich nur umbenennen.
 */
function EditCategoryDialog({ category, categories, onClose }: { category: Category; categories: Category[]; onClose: () => void }) {
  const update = useUpdateCategory();
  const notify = useToast();
  const income = category.type === 'income';
  const hasSubs = categories.some((c) => c.parent_id === category.id);
  const mains = categories
    .filter((c) => c.parent_id === null && c.id !== category.id && (c.type === 'income') === income)
    .sort(byName);
  const [name, setName] = useState(category.name);
  const [parent, setParent] = useState(category.parent_id === null ? '' : String(category.parent_id));
  const [error, setError] = useState('');

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!name.trim()) {
      setError('Bitte einen Namen eingeben.');
      return;
    }
    update.mutate({ id: category.id, body: { name: name.trim(), parent_id: parent ? Number(parent) : null } }, {
      onSuccess: () => { notify(`${name.trim()} gespeichert`); onClose(); },
      onError: (failure) => setError(failure.message),
    });
  };

  return (
    <Dialog title="Kategorie bearbeiten" onClose={onClose} busy={update.isPending}>
      <form className="dialog-form" onSubmit={submit} noValidate>
        <div className="field">
          <label htmlFor="edit-category-name">Name</label>
          <input className="input" id="edit-category-name" maxLength={60} value={name} onChange={(e) => setName(e.target.value)}
            aria-invalid={error ? true : undefined} />
        </div>
        <div className="field">
          <label htmlFor="edit-category-parent">Einordnen unter</label>
          <select className="select" id="edit-category-parent" value={parent} onChange={(e) => setParent(e.target.value)} disabled={hasSubs}
            aria-describedby={hasSubs ? 'edit-category-hint' : undefined}>
            <option value="">Als eigene Hauptkategorie</option>
            {mains.map((m) => <option key={m.id} value={m.id}>{income ? m.name : `${m.name} (${TYPE_LABEL[m.type]})`}</option>)}
          </select>
          {hasSubs && <p className="hint" id="edit-category-hint">Hat Unterkategorien und bleibt deshalb eine Hauptkategorie.</p>}
        </div>
        <p className="hint">Die Buchungen dieser Kategorie bleiben erhalten und wandern mit.</p>
        {error && <p className="err" role="alert">{error}</p>}
        <div className="dialog-actions">
          <button type="button" className="btn" onClick={onClose} disabled={update.isPending}>Abbrechen</button>
          <button type="submit" className="btn btn-primary" disabled={update.isPending}>{update.isPending ? 'Speichert …' : 'Speichern'}</button>
        </div>
      </form>
    </Dialog>
  );
}

function DeleteCategoryDialog({ category, subs, onClose }: { category: Category; subs: Category[]; onClose: () => void }) {
  const remove = useDeleteCategory();
  const notify = useToast();
  const confirm = () => remove.mutate(category.id, {
    onSuccess: () => { notify(`${category.name} gelöscht`); onClose(); },
  });
  return (
    <Dialog title={`${category.name} löschen?`} onClose={onClose} busy={remove.isPending}>
      <p className="muted">
        {subs.length
          ? `Die Unterkategorien ${subs.map((s) => s.name).join(', ')} werden mitgelöscht. `
          : ''}
        Das geht nur, solange keine Buchungen daran hängen. Sonst ordne sie vorher im Haushaltsbuch um.
      </p>
      {remove.isError && <p className="err" role="alert">{remove.error.message}</p>}
      <div className="dialog-actions">
        <button className="btn" onClick={onClose} disabled={remove.isPending} data-autofocus>Abbrechen</button>
        <button className="btn btn-danger" onClick={confirm} disabled={remove.isPending}>{remove.isPending ? 'Löscht …' : 'Löschen'}</button>
      </div>
    </Dialog>
  );
}
