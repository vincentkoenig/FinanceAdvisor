import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { renderApp } from '../../test/renderApp';
import { data, sent, session } from '../../test/server';

beforeEach(() => {
  session.loggedIn = true;
  vi.useFakeTimers({ toFake: ['Date'] });
  vi.setSystemTime(new Date(2026, 9, 30, 10));
});
afterEach(() => vi.useRealTimers());

const region = (name: string) => screen.findByRole('region', { name });

describe('Verträge', () => {
  it('ist über "Mehr" erreichbar', async () => {
    const { router } = renderApp('/');
    const user = userEvent.setup();
    await user.click(await screen.findByRole('button', { name: 'Mehr' }));
    await user.click(within(await screen.findByRole('dialog', { name: 'Mehr' })).getByRole('link', { name: /Verträge/ }));
    expect(await screen.findByRole('heading', { name: 'Verträge', level: 1 })).toBeInTheDocument();
    expect(router.state.location.pathname).toBe('/contracts');
  });

  it('zeigt die Kosten aller laufenden Verträge und die nächste Frist', async () => {
    renderApp('/contracts');
    const hero = await region('Verträge kosten im Monat');
    await waitFor(() => expect(hero).toHaveTextContent('Verträge kosten im Monat68,88 €'));
    expect(hero).toHaveTextContent('826,56 € im Jahr · 4 laufende Verträge');
    expect(screen.getByText(/Nächste Frist: Haftpflicht bis 30.11.2026 kündbar/)).toHaveTextContent('(in 31 Tagen)');
  });

  it('listet nur Fristen der nächsten 60 Tage unter "Bald kündbar", ohne monatlich kündbare Abos', async () => {
    renderApp('/contracts');
    const soon = await region('Bald kündbar');
    await waitFor(() => expect(within(soon).getAllByRole('button')).toHaveLength(1));
    expect(soon).toHaveTextContent('Haftpflichtbis 30.11.2026 zum 31.12.2026in 31 Tagen');
  });

  it('gruppiert alle Verträge nach Art mit Frist oder Ende', async () => {
    renderApp('/contracts');
    const all = await region('Alle Verträge');
    await waitFor(() => expect(within(all).getAllByRole('heading', { level: 3 }).map((h) => h.textContent))
      .toEqual(['Versicherungen', 'Handy & Internet', 'Abos & Streaming', 'Fitness']));
    const rows = within(all).getAllByRole('button').map((b) => b.textContent);
    expect(rows).toEqual([
      'HaftpflichtBeispiel Versicherung · kündbar bis 30.11.2026 zum 31.12.202660,00 €jährlich',
      'Handykündbar bis 14.02.2027 zum 14.03.202719,99 €monatlich',
      'Streamingmonatlich kündbar, frühestens zum 02.11.202613,99 €monatlich',
      'Fitnessstudiogekündigtgekündigt, endet am 31.12.202629,90 €monatlich',
    ]);
  });

  it('legt einen Vertrag an und schlägt übliche Bedingungen je Art vor', async () => {
    renderApp('/contracts');
    const user = userEvent.setup();
    await user.click(await screen.findByRole('button', { name: 'Vertrag' }));
    const box = await screen.findByRole('dialog', { name: 'Vertrag hinzufügen' });

    await user.click(within(box).getByRole('button', { name: 'Speichern' }));
    expect(within(box).getByText('Bitte einen Namen eingeben.')).toBeInTheDocument();
    expect(within(box).getByText('Bitte einen Beitrag größer 0 eingeben.')).toBeInTheDocument();

    await user.selectOptions(within(box).getByLabelText('Art'), 'telecom');
    expect(within(box).getByLabelText('Mindestlaufzeit in Monaten')).toHaveValue('24');
    expect(within(box).getByLabelText('Verlängert sich danach')).toHaveDisplayValue('jeden Monat');
    expect(within(box).getByLabelText('Kündigungsfrist')).toHaveValue('1');

    await user.type(within(box).getByLabelText('Name'), 'Internet');
    await user.type(within(box).getByLabelText('Anbieter'), 'Beispiel Telekom');
    await user.type(within(box).getByLabelText('Beitrag'), '39,99');
    await user.clear(within(box).getByLabelText('Beginn'));
    await user.type(within(box).getByLabelText('Beginn'), '2026-01-01');
    await user.click(within(box).getByRole('button', { name: 'Speichern' }));

    expect(await screen.findByText('Internet gespeichert: kündbar bis 30.09.2027 zum 31.12.2027')).toBeInTheDocument();
    expect(sent.contract).toEqual({
      name: 'Internet', provider: 'Beispiel Telekom', category: 'telecom', contract_number: null, amount: 39.99,
      interval: 'monthly', start_date: '2026-01-01', min_term_months: 24, renewal_months: 1, notice_value: 1,
      notice_unit: 'months', notes: null,
    });
    await waitFor(() => expect(screen.getByText('Internet')).toBeInTheDocument());
  });

  it('behält von Hand geänderte Bedingungen beim Wechsel der Art', async () => {
    renderApp('/contracts');
    const user = userEvent.setup();
    await user.click(await screen.findByRole('button', { name: 'Vertrag' }));
    const box = await screen.findByRole('dialog');
    await user.clear(within(box).getByLabelText('Kündigungsfrist'));
    await user.type(within(box).getByLabelText('Kündigungsfrist'), '6');
    await user.selectOptions(within(box).getByLabelText('Art'), 'Fitness');
    expect(within(box).getByLabelText('Kündigungsfrist')).toHaveValue('6');
  });

  it('bearbeitet einen Vertrag', async () => {
    renderApp('/contracts');
    const user = userEvent.setup();
    const all = await region('Alle Verträge');
    await user.click(await within(all).findByRole('button', { name: /^Handy/ }));
    const box = await screen.findByRole('dialog', { name: 'Handy' });
    expect(within(box).getByLabelText('Beitrag')).toHaveValue('19,99');
    await user.clear(within(box).getByLabelText('Beitrag'));
    await user.type(within(box).getByLabelText('Beitrag'), '24,99');
    await user.click(within(box).getByRole('button', { name: 'Speichern' }));

    expect(await screen.findByText(/^Handy gespeichert/)).toBeInTheDocument();
    expect(sent.contract).toMatchObject({ amount: 24.99, min_term_months: 24, renewal_months: 1 });
  });

  it('markiert einen Vertrag als gekündigt, zum nächstmöglichen Termin vorgeschlagen', async () => {
    renderApp('/contracts');
    const user = userEvent.setup();
    const all = await region('Alle Verträge');
    await user.click(await within(all).findByRole('button', { name: /^Haftpflicht/ }));
    await user.click(within(await screen.findByRole('dialog')).getByRole('button', { name: 'Als gekündigt markieren' }));

    const box = await screen.findByRole('dialog', { name: 'Haftpflicht kündigen' });
    expect(within(box).getByLabelText('Endet am')).toHaveValue('2026-12-31');
    expect(box).toHaveTextContent('Nächstmöglich: 31.12.2026');
    await user.click(within(box).getByRole('button', { name: 'Als gekündigt markieren' }));

    expect(await screen.findByText('Haftpflicht gekündigt, endet am 31.12.2026')).toBeInTheDocument();
    expect(sent.cancel).toEqual({ id: 51, end_date: '2026-12-31' });
    await waitFor(() => expect(within(all).getAllByText('gekündigt')).toHaveLength(2));
  });

  it('nimmt eine Kündigung zurück', async () => {
    renderApp('/contracts');
    const user = userEvent.setup();
    const all = await region('Alle Verträge');
    await user.click(await within(all).findByRole('button', { name: /^Fitnessstudio/ }));
    await user.click(within(await screen.findByRole('dialog')).getByRole('button', { name: 'Kündigung zurücknehmen' }));
    expect(await screen.findByText('Kündigung von Fitnessstudio zurückgenommen')).toBeInTheDocument();
    await waitFor(() => expect(within(all).queryByText('gekündigt')).not.toBeInTheDocument());
  });

  it('löscht erst nach Rückfrage', async () => {
    renderApp('/contracts');
    const user = userEvent.setup();
    const all = await region('Alle Verträge');
    await user.click(await within(all).findByRole('button', { name: /^Handy/ }));
    await user.click(within(await screen.findByRole('dialog')).getByRole('button', { name: 'Löschen' }));
    const box = await screen.findByRole('dialog', { name: 'Handy löschen?' });
    await user.click(within(box).getByRole('button', { name: 'Löschen' }));
    expect(await screen.findByText('Handy gelöscht')).toBeInTheDocument();
    await waitFor(() => expect(within(all).getAllByRole('button')).toHaveLength(3));
  });

  it('erklärt die leere Seite', async () => {
    data.contracts = [];
    renderApp('/contracts');
    expect(await screen.findByText(/Noch keine Verträge/)).toBeInTheDocument();
    expect(screen.getByText('In den nächsten 60 Tagen endet keine Kündigungsfrist.')).toBeInTheDocument();
    expect(screen.getByText('Versicherungen, Strom, Handy und Abos an einem Ort')).toBeInTheDocument();
  });
});
