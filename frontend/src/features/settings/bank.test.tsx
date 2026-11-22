import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it } from 'vitest';
import { renderApp } from '../../test/renderApp';
import { data, sent, session } from '../../test/server';

beforeEach(() => {
  session.loggedIn = true;
});

const section = () => screen.findByRole('region', { name: 'Bankabruf' });

const connection = (changes = {}) => ({
  id: 5, aspsp_name: 'HypoVereinsbank', status: 'active' as const, valid_until: '2099-05-01T10:00:00Z',
  last_sync_at: '2026-10-29T21:30:00Z', last_error: null,
  accounts: [{ id: 9, name: 'Girokonto', iban_last4: '3000', enabled: true, synced_until: '2026-10-29' }],
  ...changes,
});

describe('Bankabruf in den Einstellungen', () => {
  it('schlägt die HVB vor und startet die Anmeldung bei der Bank', async () => {
    renderApp('/settings');
    const panel = await section();
    const select = await within(panel).findByRole('combobox', { name: 'Bank' });
    await waitFor(() => expect(select).toHaveValue('HypoVereinsbank'));

    await userEvent.setup().click(within(panel).getByRole('button', { name: 'Bei der Bank anmelden' }));

    await waitFor(() => expect(sent.bankConnect).toEqual({ aspsp_name: 'HypoVereinsbank' }));
  });

  it('zeigt Zugang und Konto und ruft auf Knopfdruck ab', async () => {
    data.bank.connections = [connection()];
    renderApp('/settings');
    const panel = await section();
    expect(await within(panel).findByText('HypoVereinsbank')).toBeInTheDocument();
    expect(within(panel).getByRole('checkbox', { name: 'Girokonto ···3000' })).toBeChecked();

    await userEvent.setup().click(within(panel).getByRole('button', { name: 'Jetzt abrufen' }));

    expect(await screen.findByText('Abgerufen: 3 gebucht, 2 zur Prüfung')).toBeInTheDocument();
  });

  it('bietet bei abgelaufener Freigabe das neue Verbinden an', async () => {
    data.bank.connections = [connection({ status: 'expired' })];
    renderApp('/settings');
    const panel = await section();

    expect(await within(panel).findByText('Freigabe abgelaufen')).toBeInTheDocument();
    await userEvent.setup().click(within(panel).getByRole('button', { name: 'Neu verbinden' }));
    await waitFor(() => expect(sent.bankConnect).toEqual({ aspsp_name: 'HypoVereinsbank' }));
  });

  it('nennt ohne Einrichtung auf dem Server die Rücksprung-Adresse', async () => {
    data.bank.configured = false;
    renderApp('/settings');
    const panel = await section();

    expect(await within(panel).findByText('http://localhost/api/v1/bank/callback')).toBeInTheDocument();
    expect(within(panel).queryByRole('button', { name: 'Bei der Bank anmelden' })).not.toBeInTheDocument();
  });

  it('meldet das Ergebnis des Rücksprungs von der Bank', async () => {
    renderApp('/settings?bank=verbunden');

    expect(await screen.findByText(/Bank verbunden/)).toBeInTheDocument();
  });
});

describe('Prüfliste vom Bankabruf', () => {
  it('weist im Haushaltsbuch auf wartende Umsätze hin', async () => {
    data.bank.review_count = 2;
    renderApp('/budget');

    const hint = (await screen.findByText(/2 Umsätze vom Bankabruf warten/)).closest('.bank-waiting') as HTMLElement;
    expect(hint).toHaveTextContent('2 Umsätze vom Bankabruf warten auf deine Prüfung');
    expect(within(hint).getByRole('link', { name: 'Prüfen' })).toHaveAttribute('href', '/budget/import?source=bank');
  });

  it('bucht ausgewählte Umsätze und verwirft abgewählte', async () => {
    renderApp('/budget/import?source=bank');
    const user = userEvent.setup();
    expect(await screen.findByRole('heading', { name: 'Umsätze von der Bank prüfen', level: 1 })).toBeInTheDocument();
    expect(screen.queryByText('Datei wählen')).not.toBeInTheDocument();

    // Laden B hat keine Kategorie: abwählen, dann bleibt nur Laden A zum Buchen
    const groupB = await screen.findByRole('checkbox', { name: /Laden B/ });
    await user.click(groupB);
    await user.click(screen.getByRole('button', { name: '1 Umsatz übernehmen' }));

    await waitFor(() => expect(sent.bankReview).toEqual({
      book: [{ id: 71, category_id: 2, description: 'Laden A' }], dismiss: [72],
    }));
    expect(await screen.findByText('1 Umsätze übernommen, 1 verworfen')).toBeInTheDocument();
  });

  it('sagt, wenn nichts wartet', async () => {
    data.bankReview = [];
    renderApp('/budget/import?source=bank');

    expect(await screen.findByText('Keine Umsätze warten auf Prüfung.')).toBeInTheDocument();
  });
});
