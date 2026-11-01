import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { renderApp } from '../../test/renderApp';
import { sent, session } from '../../test/server';

beforeEach(() => {
  session.loggedIn = true;
  vi.useFakeTimers({ toFake: ['Date'] });
  vi.setSystemTime(new Date(2026, 9, 30, 10));
});
afterEach(() => vi.useRealTimers());

const csv = (text: string) => new File([text], 'umsaetze.csv', { type: 'text/csv' });

async function openWithFile(text = 'Buchungsdatum;Empfänger;Betrag\n') {
  const { router } = renderApp('/budget/import');
  const user = userEvent.setup();
  await user.upload(await screen.findByLabelText('CSV-Datei wählen'), csv(text));
  return { user, router };
}

const preview = () => screen.findByRole('region', { name: 'Vorschau' });

describe('Umsätze importieren', () => {
  it('ist aus dem Haushaltsbuch erreichbar', async () => {
    const { router } = renderApp('/budget');
    const user = userEvent.setup();
    await user.click(await screen.findByRole('link', { name: 'Importieren' }));
    expect(await screen.findByRole('heading', { name: 'Umsätze importieren', level: 1 })).toBeInTheDocument();
    expect(router.state.location.pathname).toBe('/budget/import');
  });

  it('zeigt die Vorschau mit Status, Vorschlag und Zusammenfassung', async () => {
    await openWithFile();
    const panel = await preview();
    expect(panel).toHaveTextContent('4 neu · 1 schon erfasst · 1 schon importiert · 1 übersprungen');
    expect(panel).toHaveTextContent('schon erfasst: Miete');
    expect(panel).toHaveTextContent('schon importiert');
    expect(within(panel).getByLabelText('Kategorie für REWE Markt am 5. Okt.')).toHaveDisplayValue('Lebenshaltung · Lebensmittel');
    // Erfasste und importierte Umsätze sind nicht wählbar
    expect(within(panel).getByLabelText('Vermieter am 2. Okt. übernehmen')).toBeDisabled();
    expect(within(panel).getByLabelText('Streaming am 30. Sept. übernehmen')).not.toBeChecked();
    expect(panel).toHaveTextContent('Bei 3 ausgewählten Umsätzen fehlt noch die Kategorie.');
    expect(within(panel).getByRole('button', { name: '4 Umsätze übernehmen' })).toBeDisabled();
  });

  it('ordnet gleiche Empfänger mit zu, bietet je Richtung passende Kategorien und übernimmt', async () => {
    const { user, router } = await openWithFile();
    const panel = await preview();
    // Einnahmen bekommen nur Einkommens-Kategorien
    const refund = within(panel).getByLabelText('Kategorie für Erstattung am 9. Okt.');
    expect(within(refund).getAllByRole('option').map((o) => o.textContent)).toEqual(['Kategorie wählen', 'Einkommen · Lohn']);

    await user.selectOptions(within(panel).getByLabelText('Kategorie für Café Mitte am 7. Okt.'), '4');
    expect(within(panel).getByLabelText('Kategorie für Café Mitte am 8. Okt.')).toHaveDisplayValue('Lebenshaltung · Kleidung');
    await user.click(within(panel).getByLabelText('Erstattung am 9. Okt. übernehmen'));
    await user.click(within(panel).getByRole('button', { name: '3 Umsätze übernehmen' }));

    expect(await screen.findByText('3 Umsätze übernommen')).toBeInTheDocument();
    expect(sent.bankImport).toEqual([
      { date: '2026-10-05', amount: -54.9, counterparty: 'REWE Markt', purpose: 'Kartenzahlung', occurrence: 0, description: 'REWE Markt', category_id: 2 },
      { date: '2026-10-07', amount: -3.2, counterparty: 'Café Mitte', purpose: 'Kartenzahlung', occurrence: 0, description: 'Café Mitte', category_id: 4 },
      { date: '2026-10-08', amount: -4.5, counterparty: 'Café Mitte', purpose: 'Kartenzahlung', occurrence: 0, description: 'Café Mitte', category_id: 4 },
    ]);
    await waitFor(() => expect(router.state.location.pathname).toBe('/budget'));
  });

  it('fragt nach den Spalten, wenn sie nicht erkannt wurden', async () => {
    const { user } = await openWithFile('Tag;Wer;Wie viel\n01.10.2026;Laden;-10,00\n');
    const panel = await screen.findByRole('region', { name: 'Spalten zuordnen' });
    expect(panel).toHaveTextContent('Die Spalten wurden nicht erkannt.');
    await user.selectOptions(within(panel).getByLabelText('Datum'), 'Tag');
    await user.selectOptions(within(panel).getByLabelText('Betrag (mit Vorzeichen)'), 'Wie viel');
    await user.selectOptions(within(panel).getByLabelText('Empfänger / Auftraggeber'), 'Wer');
    await user.click(within(panel).getByRole('button', { name: 'Vorschau laden' }));

    expect(await preview()).toBeInTheDocument();
    expect(sent.mapping).toEqual({ columns: { date: 0, amount: 2, counterparty: 1 } });
    expect(screen.queryByRole('region', { name: 'Spalten zuordnen' })).not.toBeInTheDocument();
  });
});
