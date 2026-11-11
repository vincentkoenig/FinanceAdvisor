import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { renderApp } from '../../test/renderApp';
import { session } from '../../test/server';
import { fakeShareCache } from '../../test/shareCache';

beforeEach(() => {
  session.loggedIn = true;
});
afterEach(() => vi.unstubAllGlobals());

const pdf = (name: string) => new File(['%PDF-1.4'], name, { type: 'application/pdf' });
const target = () => screen.findByRole('region', { name: 'Importieren nach' });

describe('Geteilte Dateien (Teilen auf Android)', () => {
  it('zeigt die Datei und führt ins Haushaltsbuch, das sie gleich liest', async () => {
    const store = fakeShareCache([pdf('Kontoauszug.pdf')]);
    const { router } = renderApp('/import/shared');
    const user = userEvent.setup();
    expect(await screen.findByRole('region', { name: '1 Datei' })).toHaveTextContent('Kontoauszug.pdf');
    // Erst nachsehen löscht nichts
    expect(store.size).toBe(1);

    await user.click(within(await target()).getByRole('button', { name: /Haushaltsbuch/ }));
    expect(await screen.findByRole('region', { name: 'Vorschau' })).toHaveTextContent('2 neu');
    expect(router.state.location.pathname).toBe('/budget/import');
    expect(store.size).toBe(0);
  });

  it('führt mehrere Abrechnungen ins Depot, das alle liest', async () => {
    const store = fakeShareCache([pdf('kauf.pdf'), pdf('verkauf.pdf')]);
    const { router } = renderApp('/import/shared');
    const user = userEvent.setup();
    const panel = await target();
    // Das Haushaltsbuch nimmt nur eine Datei
    expect(within(panel).getByRole('button', { name: /Haushaltsbuch/ })).toBeDisabled();

    await user.click(within(panel).getByRole('button', { name: /Depot/ }));
    const files = await screen.findByRole('region', { name: 'Dateien' });
    await waitFor(() => expect(files).toHaveTextContent('2 gelesen'));
    expect(files).toHaveTextContent('kauf.pdf');
    expect(files).toHaveTextContent('verkauf.pdf');
    expect(router.state.location.pathname).toBe('/portfolio/import');
    expect(router.state.location.search).toBe('');
    expect(store.size).toBe(0);
  });

  it('lässt ein ZIP nur ins Depot', async () => {
    fakeShareCache([new File(['PK'], 'abrechnungen.zip', { type: 'application/zip' })]);
    renderApp('/import/shared');
    const panel = await target();
    expect(within(panel).getByRole('button', { name: /Haushaltsbuch/ })).toBeDisabled();
    expect(within(panel).getByRole('button', { name: /Depot/ })).toBeEnabled();
  });

  it('verwirft die Dateien auf Wunsch', async () => {
    const store = fakeShareCache([pdf('egal.pdf')]);
    const { router } = renderApp('/import/shared');
    await userEvent.setup().click(within(await target()).getByRole('button', { name: 'Verwerfen' }));
    await waitFor(() => expect(router.state.location.pathname).toBe('/'));
    expect(store.size).toBe(0);
  });

  it('sagt Bescheid, wenn nichts angekommen ist (etwa ohne Service Worker)', async () => {
    fakeShareCache([]);
    renderApp('/import/shared');
    expect(await screen.findByRole('alert')).toHaveTextContent('Die geteilte Datei ist nicht angekommen.');
    expect(screen.getByRole('link', { name: 'Abrechnungen importieren' })).toBeInTheDocument();
  });

  it('meldet im Depot, wenn beim Abholen nichts mehr da ist', async () => {
    fakeShareCache([]);
    renderApp('/portfolio/import?shared=1');
    expect(await screen.findByRole('alert')).toHaveTextContent('Die geteilten Dateien sind nicht angekommen.');
  });
});
