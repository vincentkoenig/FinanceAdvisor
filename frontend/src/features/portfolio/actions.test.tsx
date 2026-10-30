import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { renderApp } from '../../test/renderApp';
import { data, sent, server, session } from '../../test/server';

beforeEach(() => {
  session.loggedIn = true;
  // Nur das Datum festhalten; Timer bleiben echt (Suche wartet 300 ms)
  vi.useFakeTimers({ toFake: ['Date'] });
  vi.setSystemTime(new Date(2026, 9, 30, 10));
});
afterEach(() => vi.useRealTimers());

const dialog = () => screen.findByRole('dialog');

async function openTab(name: RegExp) {
  await userEvent.setup().click(await screen.findByRole('tab', { name }));
}

describe('Asset hinzufügen', () => {
  it('sucht, schlägt beim bekannten Asset den Kurs vor und speichert den Kauf', async () => {
    renderApp('/portfolio');
    const user = userEvent.setup();
    await user.click(await screen.findByRole('button', { name: 'Asset hinzufügen' }));
    const box = await dialog();
    await user.type(within(box).getByLabelText('Name, Symbol oder ISIN'), 'SAP');
    await user.click(await within(box).findByRole('option', { name: /SAP SE/ }));
    await waitFor(() => expect(within(box).getByLabelText('Kaufpreis je Stück')).toHaveValue('221,5'));
    expect(within(box).getByLabelText('Kaufdatum')).toHaveValue('2026-10-30');

    // Ohne Stückzahl kein Speichern
    await user.click(within(box).getByRole('button', { name: 'Hinzufügen' }));
    expect(within(box).getByText('Bitte eine Stückzahl größer 0 eingeben.')).toBeInTheDocument();
    expect(sent.buy).toBeUndefined();

    await user.type(within(box).getByLabelText('Stück'), '2,5');
    await user.click(within(box).getByRole('button', { name: 'Hinzufügen' }));
    expect(await screen.findByText('Gekauft: 2,5 × SAP SE')).toBeInTheDocument();
    expect(sent.buy).toEqual({ asset_id: 3, quantity: 2.5, avg_buy_price: 221.5, bought_at: '2026-10-30' });
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('legt einen neuen Suchtreffer erst beim Speichern an', async () => {
    renderApp('/portfolio');
    const user = userEvent.setup();
    await user.click(await screen.findByRole('button', { name: 'Asset hinzufügen' }));
    const box = await dialog();
    await user.type(within(box).getByLabelText('Name, Symbol oder ISIN'), 'nvidia');
    await user.click(await within(box).findByRole('option', { name: /NVIDIA Corp/ }));
    expect(sent.asset).toBeUndefined();
    await user.type(within(box).getByLabelText('Stück'), '3');
    await user.type(within(box).getByLabelText('Kaufpreis je Stück'), '150,50 €');
    await user.click(within(box).getByRole('button', { name: 'Hinzufügen' }));
    await waitFor(() => expect(sent.buy).toEqual({ asset_id: 99, quantity: 3, avg_buy_price: 150.5, bought_at: '2026-10-30' }));
    expect(sent.asset).toEqual({ symbol: 'NVD.DE', name: 'NVIDIA Corp' });
  });

  it('zeigt Feldfehler der API am Feld', async () => {
    server.use(http.post('/api/v1/me/positions', () =>
      HttpResponse.json({ error: 'Ungültige Eingabe', fields: { bought_at: 'Das Kaufdatum darf nicht in der Zukunft liegen' } }, { status: 400 })));
    renderApp('/portfolio');
    const user = userEvent.setup();
    await user.click(await screen.findByRole('button', { name: 'Asset hinzufügen' }));
    const box = await dialog();
    await user.type(within(box).getByLabelText('Name, Symbol oder ISIN'), 'SAP');
    await user.click(await within(box).findByRole('option', { name: /SAP SE/ }));
    await user.type(within(box).getByLabelText('Stück'), '1');
    await user.click(within(box).getByRole('button', { name: 'Hinzufügen' }));
    expect(await within(box).findByText('Das Kaufdatum darf nicht in der Zukunft liegen')).toBeInTheDocument();
    expect(within(box).getByLabelText('Kaufdatum')).toHaveAttribute('aria-invalid', 'true');
  });

  it('schließt mit Esc', async () => {
    renderApp('/portfolio');
    const user = userEvent.setup();
    await user.click(await screen.findByRole('button', { name: 'Asset hinzufügen' }));
    await dialog();
    await user.keyboard('{Escape}');
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });
});

describe('Kauf und Verkauf einer Position', () => {
  it('verkauft höchstens die vorhandene Stückzahl', async () => {
    renderApp('/portfolio');
    const user = userEvent.setup();
    await user.click(await screen.findByRole('button', { name: 'iShares Core MSCI World' }));
    const box = await dialog();
    expect(box).toHaveTextContent('Wert10.000,00 €100 Stück');
    await user.click(within(box).getByRole('button', { name: 'Verkauf' }));
    expect(within(box).getByLabelText('Verkaufspreis je Stück')).toHaveValue('100');
    expect(within(box).queryByLabelText('Kaufdatum')).not.toBeInTheDocument();

    await user.type(within(box).getByLabelText('Stück'), '200');
    await user.click(within(box).getByRole('button', { name: 'Verkauf speichern' }));
    expect(within(box).getByText('Du hast nur 100 Stück.')).toBeInTheDocument();

    await user.clear(within(box).getByLabelText('Stück'));
    await user.type(within(box).getByLabelText('Stück'), '10');
    await user.click(within(box).getByRole('button', { name: 'Verkauf speichern' }));
    expect(await screen.findByText('Verkauft: 10 × iShares Core MSCI World zu 100,00 €')).toBeInTheDocument();
    expect(sent.sell).toEqual({ asset_id: 1, quantity: 10, price: 100 });
  });

  it('kauft nach mit Datum', async () => {
    renderApp('/portfolio');
    const user = userEvent.setup();
    await user.click(await screen.findByRole('button', { name: 'Bitcoin' }));
    const box = await dialog();
    await user.type(within(box).getByLabelText('Stück'), '0,01');
    await user.clear(within(box).getByLabelText('Kaufdatum'));
    await user.type(within(box).getByLabelText('Kaufdatum'), '2026-10-12');
    await user.click(within(box).getByRole('button', { name: 'Kauf speichern' }));
    await waitFor(() => expect(sent.buy).toEqual({ asset_id: 2, quantity: 0.01, avg_buy_price: 40000, bought_at: '2026-10-12' }));
  });
});

describe('Watchlist', () => {
  it('zeigt Kurs und Entwicklung seit dem Hinzufügen', async () => {
    renderApp('/portfolio');
    await openTab(/Watchlist/);
    const row = await screen.findByRole('button', { name: /SAP SE/ });
    expect(row).toHaveTextContent('SAP.DE · beobachtet seit 01.10.2026');
    expect(row).toHaveTextContent('220,00 €+10,0 % seit 200,00 €');
  });

  it('nimmt ein neues Asset auf', async () => {
    renderApp('/portfolio');
    const user = userEvent.setup();
    await openTab(/Watchlist/);
    await user.click(await screen.findByRole('button', { name: 'Beobachten' }));
    const box = await dialog();
    expect(within(box).getByRole('heading', { name: 'Asset beobachten' })).toBeInTheDocument();
    await user.type(within(box).getByLabelText('Name, Symbol oder ISIN'), 'nvidia');
    await user.click(await within(box).findByRole('option', { name: /NVIDIA Corp/ }));
    expect(within(box).queryByLabelText('Stück')).not.toBeInTheDocument();
    await user.click(within(box).getByRole('button', { name: 'Beobachten' }));
    expect(await screen.findByText('NVIDIA Corp steht jetzt auf der Watchlist')).toBeInTheDocument();
    expect(await screen.findByRole('button', { name: /NVIDIA Corp/ })).toBeInTheDocument();
  });

  it('kauft aus der Watchlist oder entfernt das Asset', async () => {
    renderApp('/portfolio');
    const user = userEvent.setup();
    await openTab(/Watchlist/);
    await user.click(await screen.findByRole('button', { name: /SAP SE/ }));
    let box = await dialog();
    expect(within(box).getByLabelText('Kaufpreis je Stück')).toHaveValue('220');
    await user.type(within(box).getByLabelText('Stück'), '4');
    await user.click(within(box).getByRole('button', { name: 'Kaufen' }));
    await waitFor(() => expect(sent.buy).toEqual({ asset_id: 3, quantity: 4, avg_buy_price: 220, bought_at: '2026-10-30' }));

    await user.click(await screen.findByRole('button', { name: /SAP SE/ }));
    box = await dialog();
    await user.click(within(box).getByRole('button', { name: 'Von Watchlist entfernen' }));
    expect(await screen.findByText(/Noch nichts auf der Watchlist/)).toBeInTheDocument();
  });
});

describe('Sparpläne', () => {
  it('listet Fälliges zuerst und führt aus', async () => {
    renderApp('/portfolio');
    await openTab(/Sparpläne/);
    const panel = screen.getByRole('tabpanel');
    expect(await within(panel).findByText('250,00 € pro Monat')).toBeInTheDocument();
    const rows = within(panel).getAllByText(/jedes Monats/).map((el) => el.textContent);
    expect(rows).toEqual(['200,00 € am 1. jedes Monats · zuletzt 1. Sept.', '50,00 € am 15. jedes Monats · zuletzt 15. Okt.']);
    expect(panel).toHaveTextContent('nächster 15. Nov.');
    await userEvent.setup().click(within(panel).getByRole('button', { name: 'Sparplan iShares Core MSCI World ausführen' }));
    expect(await screen.findByText('Sparplan ausgeführt: 1,98 Stück zu 101,00 €')).toBeInTheDocument();
  });

  it('legt einen Sparplan für ein Asset aus Depot oder Watchlist an', async () => {
    renderApp('/portfolio');
    const user = userEvent.setup();
    await openTab(/Sparpläne/);
    await user.click(await screen.findByRole('button', { name: 'Sparplan anlegen' }));
    const box = await dialog();
    const asset = within(box).getByLabelText('Asset');
    await waitFor(() => expect(within(asset).getAllByRole('option').map((o) => o.textContent))
      .toEqual(['iShares Core MSCI World', 'Bitcoin', 'SAP SE']));
    await user.selectOptions(asset, 'SAP SE');
    await user.type(within(box).getByLabelText('Betrag im Monat'), '75');
    await user.selectOptions(within(box).getByLabelText('Ausführen am'), '5');
    await user.click(within(box).getByRole('button', { name: 'Anlegen' }));
    expect(await screen.findByText('Sparplan angelegt: 75,00 € am 5. jedes Monats')).toBeInTheDocument();
    expect(sent.plan).toEqual({ asset_id: 3, amount: 75, day_of_month: 5 });
  });

  it('löscht erst nach Rückfrage', async () => {
    renderApp('/portfolio');
    const user = userEvent.setup();
    await openTab(/Sparpläne/);
    await user.click(await screen.findByRole('button', { name: 'Sparplan Bitcoin löschen' }));
    const box = await dialog();
    expect(within(box).getByRole('heading', { name: 'Sparplan Bitcoin löschen?' })).toBeInTheDocument();
    await user.click(within(box).getByRole('button', { name: 'Löschen' }));
    expect(await screen.findByText('Sparplan Bitcoin gelöscht')).toBeInTheDocument();
    await waitFor(() => expect(screen.queryByRole('button', { name: 'Sparplan Bitcoin löschen' })).not.toBeInTheDocument());
    expect(data.savingsPlans.map((p) => p.id)).toEqual([7]);
  });
});
