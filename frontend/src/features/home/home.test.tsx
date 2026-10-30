import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { renderApp } from '../../test/renderApp';
import { data, server, session } from '../../test/server';

beforeEach(() => {
  session.loggedIn = true;
  // Nur das Datum festhalten; Timer bleiben echt, sonst warten die Anfragen ewig
  vi.useFakeTimers({ toFake: ['Date'] });
  vi.setSystemTime(new Date(2026, 9, 30, 10));
});
afterEach(() => vi.useRealTimers());

// Die Seite erscheint erst nach der Anmeldeprüfung, deshalb mit find… warten
const section = (name: string) => screen.findByRole('region', { name });
const group = (name: string) => screen.findByRole('group', { name });

describe('Übersicht', () => {
  it('zeigt Gesamtvermögen aus Depot und Cash mit den Kennzahlen', async () => {
    renderApp('/');
    const hero = await section('Gesamtvermögen');
    expect(await within(hero).findByText('16.000,00 €')).toBeInTheDocument();
    expect(hero).toHaveTextContent('Depot 14.000,00 €');
    expect(hero).toHaveTextContent('Cash 2.000,00 €');
    expect(within(hero).getByRole('img', { name: 'Depot 88 %, Cash 13 %' })).toBeInTheDocument();
    expect(hero).toHaveTextContent('Gewinn seit Kauf+1.000,00 €+7,7 % auf 13.000 € Einstand');
    expect(hero).toHaveTextContent('Übrig im Oktober1.000,00 €von 3.000,00 € Einnahmen');
    expect(await within(hero).findByText('+200,00 €')).toBeInTheDocument();
  });

  it('nennt den fälligen Sparplan unter dem Titel und in "Zu tun"', async () => {
    renderApp('/');
    const todo = await section('Zu tun');
    expect(await within(todo).findByText('1 fällig')).toBeInTheDocument();
    expect(todo).toHaveTextContent('200,00 € · fällig seit 1. Okt.');
    expect(todo).toHaveTextContent('50,00 € · am 15. Nov.');
    expect(screen.getByText('Sparplan iShares Core MSCI World seit 1. Okt. fällig')).toBeInTheDocument();
  });

  it('führt einen fälligen Sparplan aus und lädt neu', async () => {
    renderApp('/');
    const user = userEvent.setup();
    await user.click(await screen.findByRole('button', { name: 'Sparplan iShares Core MSCI World ausführen' }));
    expect(await screen.findByText('Sparplan ausgeführt: 1,98 Stück zu 101,00 €')).toBeInTheDocument();
    await waitFor(() => expect(screen.queryByText('1 fällig')).not.toBeInTheDocument());
    expect(data.savingsPlans[0].is_due).toBe(false);
  });

  it('zeigt die Meldung der API, wenn das Ausführen scheitert', async () => {
    server.use(http.post('/api/v1/me/savings-plans/:id/execute', () =>
      HttpResponse.json({ error: 'Aktueller Preis konnte nicht ermittelt werden' }, { status: 502 })));
    renderApp('/');
    await userEvent.setup().click(await screen.findByRole('button', { name: /ausführen/ }));
    expect(await screen.findByText('Aktueller Preis konnte nicht ermittelt werden')).toHaveAttribute('role', 'alert');
  });

  it('teilt den Monat in Fixkosten, Variabel, Sparplan und Frei übrig', async () => {
    renderApp('/');
    const flow = await group('Oktober im Haushaltsbuch');
    expect(await within(flow).findByRole('img', { name: 'Fixkosten 40 %, Variable Ausgaben 27 %, Investiert per Sparplan 2 %, Frei übrig 32 %' })).toBeInTheDocument();
    expect(flow).toHaveTextContent('Frei übrig950,00 €32 %');
  });

  it('listet größte Positionen, letzte Buchungen und das Tages-Update', async () => {
    renderApp('/');
    const positions = await group('Größte Positionen');
    expect(await within(positions).findByText('iShares Core MSCI World')).toBeInTheDocument();
    expect(positions).toHaveTextContent('+25,0 %');
    expect(positions).toHaveTextContent('−20,0 %');
    const bookings = await group('Letzte Buchungen');
    expect(await within(bookings).findByText('Wocheneinkauf')).toBeInTheDocument();
    expect(bookings).toHaveTextContent('−54,90 €');
    expect(bookings).toHaveTextContent('+3.000,00 €');
    expect(bookings).toHaveTextContent('Lebensmittel · 28. Okt.');
    expect(bookings).toHaveTextContent('Lohn · monatlich ab 1. Okt.');
    expect(await screen.findByText('Dein Depot hat diese Woche 1,4 % zugelegt.')).toBeInTheDocument();
  });

  it('erklärt leere Bereiche bei einem neuen Konto', async () => {
    data.positions = [];
    data.savingsPlans = [];
    data.transactions = [];
    data.history = [];
    data.trades = [];
    data.insight = { content: null };
    data.summary = { cumulative_balance: 0, current_month_balance: 0, current_month_income: 0, current_month_fixed: 0, current_month_variable: 0 };
    renderApp('/');
    const hero = await section('Gesamtvermögen');
    await waitFor(() => expect(hero).toHaveTextContent('Gesamtvermögen0,00 €'));
    expect(hero).toHaveTextContent('noch keine Käufe');
    expect(await screen.findByText(/Nichts zu tun/)).toBeInTheDocument();
    expect(await screen.findByText(/Noch keine Positionen/)).toBeInTheDocument();
    expect(await screen.findByText(/Noch keine Buchungen/)).toBeInTheDocument();
    expect(await screen.findByText(/Für diesen Monat gibt es noch keine Buchungen/)).toBeInTheDocument();
    expect(await screen.findByText(/Das Tages-Update erscheint jeden Morgen/)).toBeInTheDocument();
  });

  it('bietet bei einem Ladefehler einen neuen Versuch an', async () => {
    let fail = true;
    server.use(http.get('/api/v1/me/insight', () =>
      fail ? HttpResponse.json({ error: 'kaputt' }, { status: 503 }) : HttpResponse.json(data.insight)));
    renderApp('/');
    const insight = await group('Tages-Update');
    expect(await within(insight).findByText('Konnte nicht geladen werden.')).toBeInTheDocument();
    fail = false;
    await userEvent.setup().click(within(insight).getByRole('button', { name: 'Erneut versuchen' }));
    expect(await within(insight).findByText('Dein Depot hat diese Woche 1,4 % zugelegt.')).toBeInTheDocument();
  });
});
