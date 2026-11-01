import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { beforeEach, describe, expect, it } from 'vitest';
import { renderApp } from '../../test/renderApp';
import { data, server, session } from '../../test/server';

beforeEach(() => {
  session.loggedIn = true;
});

describe('Analyse', () => {
  it('ist über das Kontomenü erreichbar', async () => {
    const { router } = renderApp('/');
    const user = userEvent.setup();
    await user.click(await screen.findByRole('button', { name: 'Konto' }));
    await user.click(within(screen.getByRole('menu')).getByRole('menuitem', { name: 'Analyse' }));
    expect(await screen.findByRole('heading', { name: 'Analyse', level: 1 })).toBeInTheDocument();
    expect(router.state.location.pathname).toBe('/analyse');
  });

  it('zeigt die neueste Analyse mit Risiko, Empfehlungen und Streuung', async () => {
    renderApp('/analyse');
    const summary = await screen.findByRole('region', { name: 'Einschätzung' });
    expect(summary).toHaveTextContent('Das Depot ist breit über einen Welt-ETF gestreut.');
    expect(summary).toHaveTextContent('Mittleres Risiko durch den Bitcoin-Anteil.');
    expect(within(summary).getAllByRole('listitem').map((li) => li.textContent)).toEqual(['Krypto-Anteil im Blick behalten', 'Notgroschen prüfen']);
    const score = screen.getByRole('region', { name: 'Streuung' });
    expect(within(score).getByRole('img', { name: 'Streuung 5 von 10' })).toBeInTheDocument();
    expect(score).toHaveTextContent('Depotwert bei der Analyse14.000,00 €');
    expect(screen.getByText(/Zuletzt am 30.10.2026 · Streuung 5 von 10/)).toBeInTheDocument();
  });

  it('klappt frühere Analysen auf', async () => {
    renderApp('/analyse');
    const older = await screen.findByRole('region', { name: 'Frühere Analysen' });
    const entry = within(older).getByText('01.09.2026 10:30').closest('details')!;
    expect(entry).not.toHaveAttribute('open');
    await userEvent.setup().click(within(older).getByText('01.09.2026 10:30'));
    expect(entry).toHaveAttribute('open');
    expect(entry).toHaveTextContent('Hohes Risiko.');
  });

  it('erstellt eine neue Analyse', async () => {
    renderApp('/analyse');
    await userEvent.setup().click(await screen.findByRole('button', { name: 'Neue Analyse' }));
    expect(await screen.findByText('Neue Analyse erstellt')).toBeInTheDocument();
    expect(await screen.findByText('Frische Analyse.')).toBeInTheDocument();
  });

  it('meldet, wenn die API ablehnt', async () => {
    server.use(http.post('/api/v1/me/analyses', () =>
      HttpResponse.json({ error: 'Zu viele Anfragen, bitte warte kurz' }, { status: 429 })));
    renderApp('/analyse');
    await userEvent.setup().click(await screen.findByRole('button', { name: 'Neue Analyse' }));
    expect(await screen.findByText('Zu viele Anfragen, bitte warte kurz')).toHaveAttribute('role', 'alert');
  });

  it('braucht für eine Analyse mindestens eine Position', async () => {
    data.analyses = [];
    data.positions = [];
    renderApp('/analyse');
    expect(await screen.findByText('Für eine Analyse braucht dein Depot mindestens eine Position.')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Neue Analyse' })).toBeDisabled();
  });
});
