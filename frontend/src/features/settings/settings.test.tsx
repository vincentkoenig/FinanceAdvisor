import { screen, waitFor } from '@testing-library/react';
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
