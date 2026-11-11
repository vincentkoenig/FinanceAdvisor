import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { renderApp } from '../../test/renderApp';
import { sent, session, testUser } from '../../test/server';

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

  it('fasst neue Umsätze je Empfänger zusammen und zeigt Status, Vorschlag und Zusammenfassung', async () => {
    const { user } = await openWithFile();
    const panel = await preview();
    expect(panel).toHaveTextContent('4 neu · 1 schon erfasst · 1 schon importiert · 1 übersprungen');
    // Café Mitte zweimal -> eine Gruppe mit beiden Umsätzen und Summe
    expect(within(panel).getByRole('button', { name: 'Café Mitte: 2 Umsätze zeigen' })).toHaveTextContent('2 Umsätze · Okt. 2026');
    expect(panel).toHaveTextContent('−7,70 €');
    expect(within(panel).getByLabelText('Kategorie für REWE Markt')).toHaveDisplayValue('Lebenshaltung · Lebensmittel');
    expect(within(panel).getByRole('button', { name: 'REWE Markt: 1 Umsätze zeigen' })).toHaveTextContent('Händler');
    // Erfasste und importierte Umsätze stehen eingeklappt darunter und sind nicht wählbar
    expect(panel).toHaveTextContent('Schon erfasst oder importiert (2)');
    expect(within(panel).getByLabelText('Vermieter am 2. Okt. übernehmen')).toBeDisabled();
    expect(panel).toHaveTextContent('Bei 3 ausgewählten Umsätzen fehlt noch die Kategorie.');
    expect(within(panel).getByRole('button', { name: '4 Umsätze übernehmen' })).toBeDisabled();

    // Aufklappen zeigt die einzelnen Umsätze
    await user.click(within(panel).getByRole('button', { name: 'Café Mitte: 2 Umsätze zeigen' }));
    expect(within(panel).getByLabelText('Kategorie für Café Mitte am 8. Okt.')).toBeInTheDocument();
  });

  it('filtert nach Richtung und fehlender Kategorie', async () => {
    const { user } = await openWithFile();
    const panel = await preview();
    await user.click(within(panel).getByRole('button', { name: 'Einnahmen (1)' }));
    expect(within(panel).queryByLabelText('Kategorie für REWE Markt')).not.toBeInTheDocument();
    expect(within(panel).getByLabelText('Kategorie für Erstattung')).toBeInTheDocument();

    await user.click(within(panel).getByRole('button', { name: 'Alle (3)' }));
    await user.click(within(panel).getByLabelText('Nur ohne Kategorie (2)'));
    expect(within(panel).queryByLabelText('Kategorie für REWE Markt')).not.toBeInTheDocument();
    expect(within(panel).getByLabelText('Kategorie für Café Mitte')).toBeInTheDocument();
  });

  it('ordnet den Rest je Richtung einer Sammelkategorie zu', async () => {
    const { user } = await openWithFile();
    const panel = await preview();
    await user.click(within(panel).getByRole('button', { name: 'Rest zuordnen …' }));

    const box = await screen.findByRole('dialog', { name: 'Rest zuordnen' });
    await user.selectOptions(within(box).getByLabelText('2 Ausgaben'), 'Versicherungen · Sonstige Versicherungen');
    await user.selectOptions(within(box).getByLabelText('1 Einnahmen'), 'Einkommen · Lohn');
    await user.click(within(box).getByRole('button', { name: 'Zuordnen' }));

    expect(await screen.findByText('3 Umsätze zugeordnet')).toBeInTheDocument();
    expect(within(panel).getByLabelText('Kategorie für Café Mitte')).toHaveDisplayValue('Versicherungen · Sonstige Versicherungen');
    // Vorhandene Vorschläge bleiben
    expect(within(panel).getByLabelText('Kategorie für REWE Markt')).toHaveDisplayValue('Lebenshaltung · Lebensmittel');
    expect(within(panel).getByRole('button', { name: '4 Umsätze übernehmen' })).toBeEnabled();
  });

  it('lässt fehlende Kategorien von der KI vorschlagen, nur mit den Namen der Empfänger', async () => {
    const { user } = await openWithFile();
    const panel = await preview();
    expect(panel).toHaveTextContent('Für 2 Empfänger ohne Kategorie');

    await user.click(within(panel).getByRole('button', { name: 'Kategorien vorschlagen lassen' }));

    expect(await screen.findByText('2 Umsätze vorbelegt, 1 neue Kategorie vorgeschlagen, bitte kurz prüfen')).toBeInTheDocument();
    // Je Name und Richtung einmal, ohne Beträge
    expect(sent.payees).toEqual([{ name: 'Café Mitte', income: false }, { name: 'Erstattung', income: true }]);
    expect(within(panel).getByLabelText('Kategorie für Café Mitte')).toHaveDisplayValue('Lebenshaltung · Kleidung');
    // Der vorhandene Vorschlag bleibt
    expect(within(panel).getByLabelText('Kategorie für REWE Markt')).toHaveDisplayValue('Lebenshaltung · Lebensmittel');
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
    await waitFor(() => expect(within(panel).getByLabelText('Kategorie für Erstattung')).toHaveDisplayValue('Einkommen · Erstattungen'));
    expect(within(panel).queryByRole('group', { name: 'Vorgeschlagene neue Kategorien' })).not.toBeInTheDocument();
  });

  it('legt aus der Kategorie-Auswahl einer Gruppe direkt eine neue Kategorie an', async () => {
    const { user } = await openWithFile();
    const panel = await preview();
    await user.selectOptions(within(panel).getByLabelText('Kategorie für Café Mitte'), '+ Neue Kategorie …');

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
    await waitFor(() => expect(within(panel).getByLabelText('Kategorie für Café Mitte')).toHaveDisplayValue('Lebenshaltung · Café'));
  });

  it('setzt die Kategorie für die ganze Gruppe, bietet je Richtung passende Kategorien und übernimmt', async () => {
    const { user, router } = await openWithFile();
    const panel = await preview();
    // Einnahmen bekommen nur Einkommens-Kategorien
    const refund = within(panel).getByLabelText('Kategorie für Erstattung');
    expect(within(refund).getAllByRole('option').map((o) => o.textContent)).toEqual(['Kategorie wählen', 'Einkommen · Lohn', '+ Neue Kategorie …']);

    await user.selectOptions(within(panel).getByLabelText('Kategorie für Café Mitte'), '4');
    await user.click(within(panel).getByLabelText('Erstattung übernehmen'));
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

  describe('über "Teilen" auf Android', () => {
    // Was der Service Worker ablegt: eine Antwort mit der Datei unter /app/share/file im Cache "fintrack-share"
    function fakeShareCache(file: File | null) {
      const store = new Map<string, Response>();
      if (file) store.set('/app/share/file', new Response(file, { headers: { 'Content-Type': file.type, 'X-File-Name': encodeURIComponent(file.name) } }));
      const cache = {
        match: async (key: string) => store.get(key),
        delete: async (key: string) => store.delete(key),
      };
      vi.stubGlobal('caches', { open: async (name: string) => (name === 'fintrack-share' ? cache : null) });
      return store;
    }
    afterEach(() => vi.unstubAllGlobals());

    it('liest die geteilte Datei gleich ein und löscht sie vom Gerät', async () => {
      const store = fakeShareCache(new File(['%PDF-1.4'], 'Kontoauszug Oktober.pdf', { type: 'application/pdf' }));
      const { router } = renderApp('/budget/import?shared=1');

      expect(await preview()).toHaveTextContent('2 neu');
      expect(screen.getByRole('region', { name: 'Datei' })).toHaveTextContent('Kontoauszug Oktober.pdf');
      expect(store.size).toBe(0);
      expect(router.state.location.search).toBe('');
    });

    it('liest die Datei auch, wenn erst die Anmeldung dazwischen kam', async () => {
      fakeShareCache(new File(['%PDF-1.4'], 'auszug.pdf', { type: 'application/pdf' }));
      session.loggedIn = false;
      renderApp('/budget/import?shared=1');
      const user = userEvent.setup();
      await user.type(await screen.findByLabelText('E-Mail'), testUser.email);
      await user.type(screen.getByLabelText('Passwort'), 'richtig');
      await user.click(screen.getByRole('button', { name: 'Anmelden' }));
      expect(await preview()).toHaveTextContent('2 neu');
    });

    it('sagt Bescheid, wenn keine Datei angekommen ist', async () => {
      fakeShareCache(null);
      renderApp('/budget/import?shared=1');
      expect(await screen.findByRole('alert')).toHaveTextContent('Die geteilte Datei ist nicht angekommen.');
    });

    it('sagt Bescheid, wenn der Server ohne Service Worker weitergeleitet hat', async () => {
      renderApp('/budget/import?shared=missing');
      expect(await screen.findByRole('alert')).toHaveTextContent('Bitte hier von Hand wählen.');
    });
  });
});
