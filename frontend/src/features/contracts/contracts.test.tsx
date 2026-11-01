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
    await user.selectOptions(within(box).getByLabelText('Im Haushaltsbuch'), 'none');
    await user.click(within(box).getByRole('button', { name: 'Speichern' }));

    expect(await screen.findByText('Internet gespeichert: kündbar bis 30.09.2027 zum 31.12.2027')).toBeInTheDocument();
    expect(sent.link).toBeUndefined();
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

  it('trägt einen neuen Vertrag anteilig als Fixkosten ins Haushaltsbuch ein', async () => {
    renderApp('/contracts');
    const user = userEvent.setup();
    await user.click(await screen.findByRole('button', { name: 'Vertrag' }));
    const box = await screen.findByRole('dialog');
    await user.type(within(box).getByLabelText('Name'), 'Hausrat');
    await user.type(within(box).getByLabelText('Beitrag'), '60');
    // Zur Art "Versicherungen" passt die Fixkosten-Kategorie unter "Versicherungen"
    await waitFor(() => expect(within(box).getByLabelText('Im Haushaltsbuch')).toHaveDisplayValue('Versicherungen · Sonstige Versicherungen'));
    expect(box).toHaveTextContent('Als Fixkosten mit 5,00 € pro Monat, ab diesem Monat');
    await user.click(within(box).getByRole('button', { name: 'Speichern' }));

    expect(await screen.findByText('Hausrat gespeichert und im Haushaltsbuch eingetragen: kündbar bis 30.09.2027 zum 31.12.2027')).toBeInTheDocument();
    expect(sent.link).toEqual({ id: expect.any(Number), category_id: 5 });
    expect(data.transactions.at(-1)).toMatchObject({ description: 'Hausrat', amount: 5, is_recurring: true });
  });

  it('schlägt eine Kategorie vor, deren Name im Vertragsnamen steckt', async () => {
    data.categories.push({ id: 6, name: 'Haftpflicht', type: 'fixed_expense', parent_id: 50 });
    renderApp('/contracts');
    const user = userEvent.setup();
    await user.click(await screen.findByRole('button', { name: 'Vertrag' }));
    const box = await screen.findByRole('dialog');
    await user.type(within(box).getByLabelText('Name'), 'Private Haftpflicht');
    await waitFor(() => expect(within(box).getByLabelText('Im Haushaltsbuch')).toHaveDisplayValue('Versicherungen · Haftpflicht'));
  });

  it('übernimmt eine vorhandene wiederkehrende Buchung', async () => {
    data.transactions.push({
      id: 200, amount: 19.99, description: 'Handyvertrag', date: '2026-01-01', end_date: null, is_recurring: true, is_paused: false,
      paused_at: null, category_id: 3, category_name: 'Miete', category_type: 'fixed_expense',
    });
    renderApp('/contracts');
    const user = userEvent.setup();
    await user.click(await within(await region('Alle Verträge')).findByRole('button', { name: /^Handy/ }));
    const box = await screen.findByRole('dialog', { name: 'Handy' });
    await waitFor(() => expect(within(box).getByRole('option', { name: 'Handyvertrag · 19,99 €' })).toBeInTheDocument());
    // Beim Bearbeiten wird nichts ungefragt eingetragen
    expect(within(box).getByLabelText('Im Haushaltsbuch')).toHaveDisplayValue('Nicht eintragen');
    await user.selectOptions(within(box).getByLabelText('Im Haushaltsbuch'), 't200');
    await user.click(within(box).getByRole('button', { name: 'Speichern' }));

    expect(await screen.findByText(/^Handy gespeichert und im Haushaltsbuch eingetragen/)).toBeInTheDocument();
    expect(sent.link).toEqual({ id: 52, transaction_id: 200 });
  });

  it('zeigt die verknüpfte Buchung und löst die Verknüpfung', async () => {
    data.contracts[0].booking = { id: 300, amount: 5, category_name: 'Sonstige Versicherungen', end_date: null };
    renderApp('/contracts');
    const user = userEvent.setup();
    await user.click(await within(await region('Alle Verträge')).findByRole('button', { name: /^Haftpflicht/ }));
    const box = await screen.findByRole('dialog', { name: 'Haftpflicht' });
    expect(box).toHaveTextContent('Im HaushaltsbuchSonstige Versicherungen · 5,00 € pro Monat');
    expect(within(box).queryByLabelText('Im Haushaltsbuch')).not.toBeInTheDocument();
    await user.click(within(box).getByRole('button', { name: 'Verknüpfung lösen' }));

    expect(await screen.findByText('Verknüpfung gelöst, die Buchung bleibt im Haushaltsbuch')).toBeInTheDocument();
    await waitFor(() => expect(within(box).getByLabelText('Im Haushaltsbuch')).toBeInTheDocument());
  });

  it('schlägt regelmäßige Abbuchungen als Vertrag vor und blendet sie aus', async () => {
    data.contractSuggestions = [
      { key: 'beispiel ag', name: 'Beispiel AG', amount: 34.38, interval: 'monthly', first_date: '2026-07-01', last_date: '2026-10-01', count: 4, category_id: 5, category_name: 'Sonstige Versicherungen', kind: 'insurance' },
      { key: 'gym', name: 'Gym', amount: 29, interval: 'monthly', first_date: '2026-08-01', last_date: '2026-10-01', count: 3, category_id: 4, category_name: 'Kleidung', kind: 'fitness' },
    ];
    renderApp('/contracts');
    const user = userEvent.setup();
    const panel = await region('Erkannt in deinen Umsätzen');
    expect(panel).toHaveTextContent('Beispiel AG34,38 € monatlich · 4× seit 1. Juli · Sonstige Versicherungen');

    await user.click(within(panel).getByRole('button', { name: 'Gym ausblenden' }));
    await waitFor(() => expect(panel).not.toHaveTextContent('Gym'));
    expect(localStorage.getItem('fintrack.contracts.dismissed')).toBe('["gym"]');

    await user.click(within(panel).getByRole('button', { name: 'Beispiel AG als Vertrag anlegen' }));
    const box = await screen.findByRole('dialog', { name: 'Vertrag hinzufügen' });
    expect(within(box).getByLabelText('Name')).toHaveValue('Beispiel AG');
    expect(within(box).getByLabelText('Beitrag')).toHaveValue('34,38');
    expect(within(box).getByLabelText('Zahlweise')).toHaveDisplayValue('monatlich');
    expect(within(box).getByLabelText('Beginn')).toHaveValue('2026-07-01');
    // Steht schon im Haushaltsbuch: nicht noch einmal als Fixkosten eintragen
    expect(within(box).getByLabelText('Im Haushaltsbuch')).toHaveDisplayValue('Nicht eintragen');
    await user.click(within(box).getByRole('button', { name: 'Speichern' }));
    expect(await screen.findByText(/^Beispiel AG gespeichert/)).toBeInTheDocument();
    expect(sent.contract).toMatchObject({ name: 'Beispiel AG', category: 'insurance', amount: 34.38, interval: 'monthly', renewal_months: 12 });
    expect(sent.link).toBeUndefined();
    localStorage.clear();
  });

  it('erklärt die leere Seite', async () => {
    data.contracts = [];
    renderApp('/contracts');
    expect(await screen.findByText(/Noch keine Verträge/)).toBeInTheDocument();
    expect(screen.getByText('In den nächsten 60 Tagen endet keine Kündigungsfrist.')).toBeInTheDocument();
    expect(screen.getByText('Versicherungen, Strom, Handy und Abos an einem Ort')).toBeInTheDocument();
  });
});
