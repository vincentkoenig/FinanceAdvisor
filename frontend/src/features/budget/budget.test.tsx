import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { renderApp } from '../../test/renderApp';
import { data, sent, session } from '../../test/server';

beforeEach(() => {
  session.loggedIn = true;
  vi.useFakeTimers({ toFake: ['Date'] });
  vi.setSystemTime(new Date(2026, 9, 30, 10));
  data.transactions.push({
    id: 13, amount: 1200, description: null, date: '2026-01-03', end_date: null, is_recurring: true, is_paused: false, paused_at: null,
    category_id: 3, category_name: 'Miete', category_type: 'fixed_expense',
  });
});
afterEach(() => vi.useRealTimers());

const hero = () => screen.findByRole('region', { name: /Übrig im/ });
// Tabelle (Laptop) und Liste (Handy) stehen beide im DOM; die Tests lesen die Tabelle
const table = () => within(screen.getByRole('region', { name: 'Buchungen' })).getByRole('table');

describe('Haushaltsbuch', () => {
  it('ist über die Navigation erreichbar', async () => {
    const { router } = renderApp('/');
    const user = userEvent.setup();
    await user.click((await screen.findAllByRole('link', { name: /Haushaltsbuch|Budget/ }))[0]);
    expect(await screen.findByRole('heading', { name: 'Haushaltsbuch', level: 1 })).toBeInTheDocument();
    expect(router.state.location.pathname).toBe('/budget');
  });

  it('zeigt, was im Monat übrig bleibt, mit Monatsfluss und Cash-Bestand', async () => {
    renderApp('/budget');
    const panel = await hero();
    await waitFor(() => expect(panel).toHaveTextContent('Übrig im Oktober1.745,10 €'));
    expect(panel).toHaveTextContent('58 % der Einnahmen · Cash-Bestand insgesamt 2.000,00 €');
    // Der Sparplan wurde im Oktober ausgeführt (50 €) und kommt aus dem freien Rest
    expect(within(panel).getByRole('img', { name: 'Fixkosten 40 %, Variable Ausgaben 2 %, Investiert per Sparplan 2 %, Frei übrig 57 %' })).toBeInTheDocument();
    expect(screen.getByText(/Größte variable Ausgabe im Oktober: Wocheneinkauf mit 54,90 €/)).toBeInTheDocument();
  });

  it('listet Ausgaben je Hauptkategorie mit Tagesschnitt', async () => {
    renderApp('/budget');
    const panel = await screen.findByRole('region', { name: 'Ausgaben nach Kategorie' });
    await waitFor(() => expect(panel).toHaveTextContent('Wohnen1.200,00 €Lebenshaltung54,90 €'));
    expect(panel).toHaveTextContent('Ausgaben gesamt1.254,90 €');
    expect(panel).toHaveTextContent('Im Schnitt pro Tag41,83 €');
  });

  it('listet die Buchungen des Monats, wiederkehrende an ihrem Tag', async () => {
    renderApp('/budget');
    await screen.findByText('3 im Oktober');
    const rows = within(table()).getAllByRole('row').slice(1).map((r) => r.textContent);
    expect(rows).toEqual([
      '28.10.WocheneinkaufLebenshaltung · Lebensmittel−54,90 €',
      '03.10.MietemonatlichWohnen · Miete−1.200,00 €',
      '01.10.GehaltmonatlichEinkommen · Lohn+3.000,00 €',
    ]);
  });

  it('blättert in andere Monate', async () => {
    renderApp('/budget');
    const user = userEvent.setup();
    await screen.findByText('3 im Oktober');
    await user.click(screen.getByRole('button', { name: 'Vorheriger Monat' }));
    expect(await screen.findByText('September 2026')).toBeInTheDocument();
    // Gehalt beginnt erst im Oktober, die Miete läuft seit Januar
    expect(await screen.findByText('1 im September')).toBeInTheDocument();
    expect(await hero()).toHaveTextContent('Übrig im September−1.200,00 €');
    expect(screen.getByText(/Die Ausgaben liegen 1.200,00 € über den Einnahmen/)).toBeInTheDocument();
  });

  it('pausiert eine wiederkehrende Buchung', async () => {
    renderApp('/budget');
    const user = userEvent.setup();
    await user.click((await screen.findAllByRole('button', { name: 'Miete pausieren' }))[0]);
    expect(await screen.findByText('Miete pausiert, zählt ab diesem Monat nicht mehr')).toBeInTheDocument();
    await waitFor(() => expect(within(table()).getAllByText('pausiert')).toHaveLength(1));
    expect(await hero()).toHaveTextContent('Übrig im Oktober2.945,10 €');
  });

  it('löscht erst nach Rückfrage und warnt bei wiederkehrenden Buchungen', async () => {
    renderApp('/budget');
    const user = userEvent.setup();
    await user.click((await screen.findAllByRole('button', { name: 'Miete löschen' }))[0]);
    const box = await screen.findByRole('dialog');
    expect(box).toHaveTextContent('Gelöscht fehlt sie in allen Monaten');
    await user.click(within(box).getByRole('button', { name: 'Löschen' }));
    expect(await screen.findByText('Miete gelöscht')).toBeInTheDocument();
    await waitFor(() => expect(screen.getByText('2 im Oktober')).toBeInTheDocument());
  });

  it('speichert eine neue Buchung mit Kategorie und Wiederholung', async () => {
    renderApp('/budget');
    const user = userEvent.setup();
    await user.click(await screen.findByRole('button', { name: 'Buchung' }));
    const box = await screen.findByRole('dialog');
    await waitFor(() => expect(within(box).getByLabelText('Unterkategorie')).toHaveValue('2'));

    await user.click(within(box).getByRole('button', { name: 'Speichern' }));
    expect(within(box).getByText('Bitte einen Betrag größer 0 eingeben.')).toBeInTheDocument();

    await user.type(within(box).getByLabelText('Betrag'), '49,99');
    await user.selectOptions(within(box).getByLabelText('Unterkategorie'), 'Kleidung');
    await user.type(within(box).getByLabelText('Beschreibung'), 'Jacke');
    await user.click(within(box).getByLabelText('Jeden Monat wiederholen'));
    expect(within(box).getByLabelText('Erstmals am')).toHaveValue('2026-10-30');
    await user.type(within(box).getByLabelText('Endet am'), '2026-12-31');
    await user.click(within(box).getByRole('button', { name: 'Speichern' }));

    expect(await screen.findByText('Buchung gespeichert: Jacke 49,99 €')).toBeInTheDocument();
    expect(sent.booking).toEqual({ category_id: 4, amount: 49.99, description: 'Jacke', date: '2026-10-30', is_recurring: true, end_date: '2026-12-31' });
    expect(await screen.findByText('4 im Oktober')).toBeInTheDocument();
  });

  it('wechselt mit der Art der Buchung die Kategorien', async () => {
    renderApp('/budget');
    const user = userEvent.setup();
    await user.click(await screen.findByRole('button', { name: 'Buchung' }));
    const box = await screen.findByRole('dialog');
    await user.click(within(box).getByRole('button', { name: 'Einnahme' }));
    expect(within(box).getByLabelText('Kategorie')).toHaveDisplayValue('Einkommen');
    expect(within(box).getByLabelText('Unterkategorie')).toHaveDisplayValue('Lohn');
  });

  it('legt bei einem neuen Konto zuerst die Kategorien an', async () => {
    data.categories = [];
    data.transactions = [];
    renderApp('/budget');
    const user = userEvent.setup();
    expect(await screen.findByText(/Keine Buchungen im Oktober. Mit „Buchung“/)).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Buchung' }));
    await user.click(await screen.findByRole('button', { name: 'Kategorien anlegen' }));
    expect(await screen.findByLabelText('Betrag')).toBeInTheDocument();
    expect(screen.getByLabelText('Unterkategorie')).toHaveDisplayValue('Lebensmittel');
  });
});
