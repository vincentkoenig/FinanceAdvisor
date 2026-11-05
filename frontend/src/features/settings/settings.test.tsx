import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { beforeEach, describe, expect, it } from 'vitest';
import { renderApp } from '../../test/renderApp';
import { sent, server, session } from '../../test/server';

beforeEach(() => {
  session.loggedIn = true;
});

const exportFile = (content: string, name = 'fintrack-export.json') =>
  new File([content], name, { type: 'application/json' });

describe('Einstellungen', () => {
  it('ist über das Kontomenü erreichbar', async () => {
    const { router } = renderApp('/');
    const user = userEvent.setup();
    await user.click(await screen.findByRole('button', { name: 'Konto' }));
    await user.click(screen.getByRole('menuitem', { name: 'Einstellungen' }));
    expect(await screen.findByRole('heading', { name: 'Einstellungen', level: 1 })).toBeInTheDocument();
    expect(router.state.location.pathname).toBe('/settings');
  });

  it('legt Unterkategorien an und löscht nur leere Kategorien', async () => {
    renderApp('/settings');
    const user = userEvent.setup();
    const section = await screen.findByRole('region', { name: 'Kategorien' });
    // Fixkosten sind vorgewählt: Hauptkategorien mit eingerückten Unterkategorien
    const list = () => within(section).getAllByRole('list')[0];
    expect(await within(section).findByText('Sonstige Versicherungen')).toBeInTheDocument();
    expect(list()).toHaveTextContent('Versicherungen');
    expect(list()).not.toHaveTextContent('Lebensmittel');

    await user.type(within(section).getByLabelText('Neue Kategorie'), 'Lebensversicherung');
    await user.selectOptions(within(section).getByLabelText('Einordnen unter'), 'Versicherungen');
    await user.click(within(section).getByRole('button', { name: 'Anlegen' }));

    expect(await screen.findByText('Versicherungen · Lebensversicherung angelegt')).toBeInTheDocument();
    expect(sent.category).toEqual({ name: 'Lebensversicherung', type: 'fixed_expense', parent_id: 50 });
    await waitFor(() => expect(list()).toHaveTextContent('Lebensversicherung'));

    // Lebenshaltung hat Buchungen (Wocheneinkauf): der Server lehnt ab, der Dialog sagt warum
    await user.click(within(section).getByRole('button', { name: 'Variable Ausgaben' }));
    await user.click(within(section).getByRole('button', { name: 'Lebenshaltung löschen' }));
    const box = await screen.findByRole('dialog');
    expect(box).toHaveTextContent('Die Unterkategorien Kleidung, Lebensmittel werden mitgelöscht');
    await user.click(within(box).getByRole('button', { name: 'Löschen' }));
    expect(await within(box).findByRole('alert')).toHaveTextContent('enthält noch Buchungen');
  });

  it('benennt eine Kategorie um und verschiebt sie unter eine andere Hauptkategorie', async () => {
    renderApp('/settings');
    const user = userEvent.setup();
    const section = await screen.findByRole('region', { name: 'Kategorien' });
    await user.click(await within(section).findByRole('button', { name: 'Versicherungen · Sonstige Versicherungen bearbeiten' }));

    const box = await screen.findByRole('dialog', { name: 'Kategorie bearbeiten' });
    // Ausgabe: nur Ausgaben-Hauptkategorien, mit Art
    expect(within(within(box).getByLabelText('Einordnen unter')).getAllByRole('option').map((o) => o.textContent)).toEqual([
      'Als eigene Hauptkategorie', 'Lebenshaltung (Variable Ausgabe)', 'Versicherungen (Fixkosten)', 'Wohnen (Fixkosten)',
    ]);
    await user.clear(within(box).getByLabelText('Name'));
    await user.type(within(box).getByLabelText('Name'), 'Lebensversicherung');
    await user.selectOptions(within(box).getByLabelText('Einordnen unter'), 'Wohnen (Fixkosten)');
    await user.click(within(box).getByRole('button', { name: 'Speichern' }));

    expect(await screen.findByText('Lebensversicherung gespeichert')).toBeInTheDocument();
    expect(sent.categoryChange).toEqual({ name: 'Lebensversicherung', parent_id: 30 });
    expect(await within(section).findByRole('button', { name: 'Wohnen · Lebensversicherung bearbeiten' })).toBeInTheDocument();

    // Hauptkategorie mit Unterkategorien: nur umbenennen
    await user.click(within(section).getByRole('button', { name: 'Wohnen bearbeiten' }));
    const main = await screen.findByRole('dialog', { name: 'Kategorie bearbeiten' });
    expect(within(main).getByLabelText('Einordnen unter')).toBeDisabled();
    expect(main).toHaveTextContent('Hat Unterkategorien und bleibt deshalb eine Hauptkategorie.');
  });

  it('zeigt Regeln für den Import, legt neue an und löscht sie', async () => {
    renderApp('/settings');
    const user = userEvent.setup();
    const section = await screen.findByRole('region', { name: 'Regeln für den Import' });
    expect(await within(section).findByText('vodafone')).toBeInTheDocument();
    expect(section).toHaveTextContent('→ Versicherungen · Sonstige Versicherungen');

    await user.type(within(section).getByLabelText('Wenn das Wort vorkommt'), 'Telekom');
    await user.selectOptions(within(section).getByLabelText('dann Kategorie'), 'Wohnen · Miete');
    await user.click(within(section).getByRole('button', { name: 'Regel speichern' }));

    expect(await screen.findByText('Regel „telekom“ gespeichert')).toBeInTheDocument();
    expect(sent.rule).toEqual({ pattern: 'Telekom', income: false, category_id: 3 });
    expect(await within(section).findByText('telekom')).toBeInTheDocument();

    await user.click(within(section).getByRole('button', { name: 'Regel vodafone löschen' }));
    await waitFor(() => expect(within(section).queryByText('vodafone')).not.toBeInTheDocument());
  });

  it('zeigt das gespeicherte Anlageprofil und speichert Änderungen', async () => {
    renderApp('/settings');
    const user = userEvent.setup();
    expect(await screen.findByLabelText('Risikoprofil')).toHaveValue('balanced');
    expect(screen.getByLabelText('Erfahrung')).toHaveValue('');
    await user.selectOptions(screen.getByLabelText('Anlagehorizont'), 'long-term');
    await user.type(screen.getByLabelText('Monatlich investierbar (€)'), '250,50');
    await user.click(screen.getByRole('button', { name: 'Speichern' }));
    expect(await screen.findByText('Anlageprofil gespeichert')).toBeInTheDocument();
    expect(sent.settings).toEqual({
      risk_profile: 'balanced', investment_experience: null, monthly_budget: 250.5, investment_horizon: 'long-term',
    });
  });

  it('lehnt einen ungültigen Betrag ab, ohne etwas zu senden', async () => {
    renderApp('/settings');
    const user = userEvent.setup();
    await user.type(await screen.findByLabelText('Monatlich investierbar (€)'), '0');
    await user.click(screen.getByRole('button', { name: 'Speichern' }));
    expect(await screen.findByText(/Bitte einen Betrag größer 0/)).toBeInTheDocument();
    expect(screen.getByLabelText('Monatlich investierbar (€)')).toHaveAttribute('aria-invalid', 'true');
    expect(sent.settings).toBeUndefined();
  });

  it('stellt das Design auf diesem Gerät um', async () => {
    renderApp('/settings');
    const user = userEvent.setup();
    await user.click(await screen.findByRole('button', { name: 'Hell' }));
    expect(screen.getByRole('button', { name: 'Hell' })).toHaveAttribute('aria-pressed', 'true');
    expect(document.documentElement.dataset.theme).toBe('light');
    expect(localStorage.getItem('fintrack-theme')).toBe('light');
  });

  it('verlinkt den Export als Download', async () => {
    renderApp('/settings');
    const link = await screen.findByRole('link', { name: 'Herunterladen' });
    expect(link).toHaveAttribute('href', '/api/v1/me/export');
    expect(link).toHaveAttribute('download');
  });

  it('importiert eine Exportdatei erst nach Bestätigung', async () => {
    renderApp('/settings');
    const user = userEvent.setup();
    const payload = { format: 'fintrack-export', version: 1 };
    await user.upload(await screen.findByLabelText('Datei wählen'), exportFile(JSON.stringify(payload)));
    const dialog = await screen.findByRole('dialog', { name: 'Daten importieren?' });
    expect(dialog).toHaveTextContent('fintrack-export.json');
    expect(sent.import).toBeUndefined();
    await user.click(screen.getByRole('button', { name: 'Importieren' }));
    expect(await screen.findByText('Importiert: 12 Buchungen, 2 Positionen, 3 Kategorien, 1 Sparpläne')).toBeInTheDocument();
    expect(sent.import).toEqual(payload);
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
  });

  it('bricht den Import ab, ohne etwas zu senden', async () => {
    renderApp('/settings');
    const user = userEvent.setup();
    await user.upload(await screen.findByLabelText('Datei wählen'), exportFile('{}'));
    await user.click(await screen.findByRole('button', { name: 'Abbrechen' }));
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    expect(sent.import).toBeUndefined();
  });

  it('meldet eine Datei, die kein JSON ist', async () => {
    renderApp('/settings');
    await userEvent.setup().upload(await screen.findByLabelText('Datei wählen'), exportFile('kein json'));
    expect(await screen.findByRole('alert')).toHaveTextContent('Die Datei ist keine gültige Exportdatei.');
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('zeigt die Meldung der API, wenn das Konto nicht leer ist', async () => {
    server.use(http.post('/api/v1/me/import', () =>
      HttpResponse.json({ error: 'Dein Konto enthält bereits Daten' }, { status: 409 })));
    renderApp('/settings');
    const user = userEvent.setup();
    await user.upload(await screen.findByLabelText('Datei wählen'), exportFile('{}'));
    await user.click(await screen.findByRole('button', { name: 'Importieren' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Dein Konto enthält bereits Daten');
  });

  it('meldet über den Konto-Bereich ab', async () => {
    const { router } = renderApp('/settings');
    await userEvent.setup().click(await screen.findByRole('button', { name: 'Abmelden' }));
    await waitFor(() => expect(router.state.location.pathname).toBe('/login'));
    expect(session.loggedIn).toBe(false);
  });
});
