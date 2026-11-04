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
  await user.upload(await screen.findByLabelText('Datei wählen'), csv(text));
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

  it('lässt fehlende Kategorien von der KI vorschlagen, nur mit den Namen der Empfänger', async () => {
    const { user } = await openWithFile();
    const panel = await preview();
    expect(panel).toHaveTextContent('Für 2 Empfänger ohne Kategorie');

    await user.click(within(panel).getByRole('button', { name: 'Kategorien vorschlagen lassen' }));

    expect(await screen.findByText('2 Umsätze vorbelegt, 1 neue Kategorie vorgeschlagen, bitte kurz prüfen')).toBeInTheDocument();
    // Je Name und Richtung einmal, ohne Beträge
    expect(sent.payees).toEqual([{ name: 'Café Mitte', income: false }, { name: 'Erstattung', income: true }]);
    expect(within(panel).getByLabelText('Kategorie für Café Mitte am 7. Okt.')).toHaveDisplayValue('Lebenshaltung · Kleidung');
    expect(within(panel).getByLabelText('Kategorie für Café Mitte am 8. Okt.')).toHaveDisplayValue('Lebenshaltung · Kleidung');
    // Der vorhandene Vorschlag bleibt
    expect(within(panel).getByLabelText('Kategorie für REWE Markt am 5. Okt.')).toHaveDisplayValue('Lebenshaltung · Lebensmittel');
    expect(panel).toHaveTextContent('Für 1 Empfänger ohne Kategorie');
  });

  it('legt eine von der KI vorgeschlagene neue Kategorie erst nach Zustimmung an und ordnet sie zu', async () => {
    const { user } = await openWithFile();
    const panel = await preview();
    await user.click(within(panel).getByRole('button', { name: 'Kategorien vorschlagen lassen' }));

    const proposals = await within(panel).findByRole('group', { name: 'Vorgeschlagene neue Kategorien' });
    expect(proposals).toHaveTextContent('Einkommen · Erstattungen');
    expect(proposals).toHaveTextContent('1 Umsatz · Erstattung');
    expect(sent.category).toBeUndefined();

    await user.click(within(proposals).getByRole('button', { name: 'Einkommen · Erstattungen anlegen und zuordnen' }));

    expect(await screen.findByText('Einkommen · Erstattungen angelegt, 1 Umsätze zugeordnet')).toBeInTheDocument();
    expect(sent.category).toEqual({ name: 'Erstattungen', type: 'income', parent_id: 10 });
    await waitFor(() => expect(within(panel).getByLabelText('Kategorie für Erstattung am 9. Okt.')).toHaveDisplayValue('Einkommen · Erstattungen'));
    expect(within(panel).queryByRole('group', { name: 'Vorgeschlagene neue Kategorien' })).not.toBeInTheDocument();
  });

  it('legt aus der Kategorie-Auswahl direkt eine neue Kategorie an', async () => {
    const { user } = await openWithFile();
    const panel = await preview();
    await user.selectOptions(within(panel).getByLabelText('Kategorie für Café Mitte am 7. Okt.'), '+ Neue Kategorie …');

    const box = await screen.findByRole('dialog', { name: 'Neue Kategorie' });
    // Ausgabe: nur Ausgaben-Hauptkategorien und neue Hauptkategorie als Fix- oder variable Kosten
    expect(within(within(box).getByLabelText('Einordnen unter')).getAllByRole('option').map((o) => o.textContent)).toEqual([
      'Lebenshaltung (Variable Ausgabe)', 'Versicherungen (Fixkosten)', 'Wohnen (Fixkosten)', 'Als eigene Hauptkategorie (Fixkosten)',
      'Als eigene Hauptkategorie (Variable Ausgabe)',
    ]);
    await user.type(within(box).getByLabelText('Name'), 'Café');
    await user.click(within(box).getByRole('button', { name: 'Anlegen und zuordnen' }));

    expect(await screen.findByText('Lebenshaltung · Café angelegt')).toBeInTheDocument();
    expect(sent.category).toEqual({ name: 'Café', type: 'variable_expense', parent_id: 20 });
    // Gleicher Empfänger bekommt sie mit
    await waitFor(() => expect(within(panel).getByLabelText('Kategorie für Café Mitte am 8. Okt.')).toHaveDisplayValue('Lebenshaltung · Café'));
  });

  it('ordnet gleiche Empfänger mit zu, bietet je Richtung passende Kategorien und übernimmt', async () => {
    const { user, router } = await openWithFile();
    const panel = await preview();
    // Einnahmen bekommen nur Einkommens-Kategorien
    const refund = within(panel).getByLabelText('Kategorie für Erstattung am 9. Okt.');
    expect(within(refund).getAllByRole('option').map((o) => o.textContent)).toEqual(['Kategorie wählen', 'Einkommen · Lohn', '+ Neue Kategorie …']);

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

  it('liest einen Kontoauszug als PDF und zeigt den gesendeten Text', async () => {
    renderApp('/budget/import');
    const user = userEvent.setup();
    await user.upload(await screen.findByLabelText('Datei wählen'), new File(['%PDF-1.4'], 'auszug.pdf', { type: 'application/pdf' }));

    const panel = await preview();
    expect(panel).toHaveTextContent('2 neu');
    const file = screen.getByRole('region', { name: 'Datei' });
    expect(within(file).getByText('Gesendeter Text')).toBeInTheDocument();
    expect(within(file).getByText('Kontoauszug [NUMMER]')).toBeInTheDocument();
    expect(sent.mapping).toBeUndefined();
  });
});
