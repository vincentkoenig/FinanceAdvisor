import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { renderApp } from '../../test/renderApp';
import { data, session } from '../../test/server';

beforeEach(() => {
  session.loggedIn = true;
  // Nur das Datum festhalten; Timer bleiben echt, sonst warten die Anfragen ewig
  vi.useFakeTimers({ toFake: ['Date'] });
  vi.setSystemTime(new Date(2026, 9, 30, 10));
});
afterEach(() => vi.useRealTimers());

const hero = () => screen.findByRole('region', { name: 'Depotwert' });
const tabPanel = () => screen.getByRole('tabpanel');
// Tabelle (Laptop) und Liste (Handy) stehen beide im DOM; die Tests lesen die Tabelle
const table = () => within(tabPanel()).getByRole('table');

describe('Portfolio', () => {
  it('ist über die Navigation erreichbar', async () => {
    const { router } = renderApp('/');
    const user = userEvent.setup();
    const nav = await screen.findAllByRole('link', { name: /Portfolio/ });
    await user.click(nav[0]);
    expect(await screen.findByRole('heading', { name: 'Portfolio', level: 1 })).toBeInTheDocument();
    expect(router.state.location.pathname).toBe('/portfolio');
  });

  it('nennt unter dem Titel, welche Position den Gewinn trägt', async () => {
    renderApp('/portfolio');
    expect(await screen.findByText(/zu deinem Gewinn von/)).toHaveTextContent(
      'iShares Core MSCI World trägt +2.000,00 € zu deinem Gewinn von 1.000,00 € bei');
  });

  it('zeigt Depotwert, Entwicklung im Zeitraum und den Wertverlauf', async () => {
    data.history = [
      { date: '2026-09-15', value: 11000 },
      { date: '2026-10-22', value: 13000 },
      { date: '2026-10-29', value: 13800 },
      { date: '2026-10-30', value: 13800 },
    ];
    renderApp('/portfolio');
    const panel = await hero();
    expect(await within(panel).findByText('14.000,00 €')).toBeInTheDocument();
    // Ein Monat: Ausgangspunkt ist der 15. Sept., heute zählt der Live-Wert
    await waitFor(() => expect(panel).toHaveTextContent('+3.000,00 € (+27,3 %) in einem Monat'));
    expect(within(panel).getByRole('img', { name: 'Depotwert vom 15. Sept. 2026 bis 30. Okt. 2026, zuletzt 14.000,00 €' })).toBeInTheDocument();

    await userEvent.setup().click(within(panel).getByRole('button', { name: '1W' }));
    expect(panel).toHaveTextContent('+1.000,00 € (+7,7 %) in einer Woche');
    expect(within(panel).getByRole('button', { name: '1W' })).toHaveAttribute('aria-pressed', 'true');
  });

  it('teilt das Depot nach Anlageart auf, als Balken oder Ring', async () => {
    renderApp('/portfolio');
    const panel = await screen.findByRole('region', { name: 'Aufteilung' });
    expect(await within(panel).findByRole('img', { name: 'ETFs 71 %, Krypto 29 %' })).toBeInTheDocument();
    expect(panel).toHaveTextContent('Einstand13.000 €');

    await userEvent.setup().click(within(panel).getByRole('button', { name: 'Als Ring' }));
    expect(within(panel).getByRole('img', { name: 'ETFs 71 %, Krypto 29 %' }).tagName).toBe('svg');
    expect(panel).toHaveTextContent('Depot14.000 €');
    expect(localStorage.getItem('ft-alloc-view')).toBe('ring');
  });

  it('listet die Positionen nach Wert und sortiert per Spaltenkopf um', async () => {
    renderApp('/portfolio');
    await screen.findByRole('tab', { name: /Positionen/, selected: true });
    const names = () => within(table()).getAllByRole('row').slice(1, -1).map((row) => within(row).getAllByRole('cell')[0].textContent);
    await waitFor(() => expect(names()).toEqual(['EUNLiShares Core MSCI WorldEUNL.DE', 'BTCBitcoinBTC-EUR']));
    expect(table()).toHaveTextContent('Gesamt14.000,00 €+1.000,00 €');

    const user = userEvent.setup();
    await user.click(within(table()).getByRole('button', { name: 'Gewinn / Verlust' }));
    expect(within(table()).getByRole('columnheader', { name: 'Gewinn / Verlust' })).toHaveAttribute('aria-sort', 'descending');
    await user.click(within(table()).getByRole('button', { name: /Gewinn/ }));
    expect(names()[0]).toContain('Bitcoin');
  });

  it('zeigt Transaktionen und Dividenden in eigenen Reitern', async () => {
    renderApp('/portfolio');
    const user = userEvent.setup();
    await user.click(await screen.findByRole('tab', { name: 'Transaktionen1' }));
    expect(table()).toHaveTextContent('02.01.2026iShares Core MSCI WorldKauf10080,00 €8.000,00 €');

    await user.click(screen.getByRole('tab', { name: /Dividenden/ }));
    expect(await within(tabPanel()).findByText('45,12 € im Jahr 2026')).toBeInTheDocument();
    expect(table()).toHaveTextContent('0,4512 €');
    expect(table()).toHaveTextContent('0,40 €');
  });

  it('erklärt leere Bereiche bei einem neuen Konto', async () => {
    data.positions = [];
    data.history = [];
    data.trades = [];
    data.dividends = [];
    renderApp('/portfolio');
    expect(await screen.findByText('Noch keine Positionen im Depot')).toBeInTheDocument();
    expect(await screen.findByText(/Der Wertverlauf erscheint/)).toBeInTheDocument();
    expect(screen.getByText(/Die Aufteilung erscheint mit der ersten Position/)).toBeInTheDocument();
    expect(screen.getByText(/Noch keine Positionen. Mit „Asset hinzufügen“/)).toBeInTheDocument();
    await userEvent.setup().click(screen.getByRole('tab', { name: /Dividenden/ }));
    expect(screen.getByText(/Noch keine Dividenden/)).toBeInTheDocument();
  });
});
