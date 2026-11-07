import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { strToU8, zipSync } from 'fflate';
import { http, HttpResponse } from 'msw';
import { beforeEach, describe, expect, it } from 'vitest';
import { renderApp } from '../../test/renderApp';
import { sent, server, session } from '../../test/server';

beforeEach(() => {
  session.loggedIn = true;
});

const pdf = (name: string, text = '%PDF-1.4') => new File([text], name, { type: 'application/pdf' });

describe('Abrechnungen importieren', () => {
  it('ist aus dem Portfolio erreichbar', async () => {
    const { router } = renderApp('/portfolio');
    const user = userEvent.setup();
    await user.click(await screen.findByRole('link', { name: 'Importieren' }));
    expect(await screen.findByRole('heading', { name: 'Abrechnungen importieren', level: 1 })).toBeInTheDocument();
    expect(router.state.location.pathname).toBe('/portfolio/import');
  });

  it('liest mehrere PDFs, zeigt den gesendeten Text und bucht nur Neues', async () => {
    const { router } = renderApp('/portfolio/import');
    const user = userEvent.setup();
    await user.upload(await screen.findByLabelText('Dateien wählen'), [pdf('kauf.pdf'), pdf('kaputt.pdf', 'kaputt')]);

    const files = await screen.findByRole('region', { name: 'Dateien' });
    await waitFor(() => expect(files).toHaveTextContent('kaputt.pdfDie Datei ist kein lesbares PDF.'));
    expect(files).toHaveTextContent('kauf.pdf2 Ausführungen');
    expect(within(files).getByText('WERTPAPIERABRECHNUNG [NUMMER]')).toBeInTheDocument();

    const preview = screen.getByRole('region', { name: 'Vorschau' });
    expect(preview).toHaveTextContent('KaufiShares Core MSCI World1. Okt. · EUNL.DE · 10 × 100,00 € · 1,00 € Gebühren1.001,00 €');
    expect(preview).toHaveTextContent('schon gebucht');
    expect(within(preview).getByLabelText('Verkauf iShares Core MSCI World am 1. Okt. buchen')).toBeDisabled();

    await user.click(within(preview).getByRole('button', { name: '1 Ausführung buchen' }));
    expect(await screen.findByText('1 Ausführungen gebucht')).toBeInTheDocument();
    expect(sent.depotImport).toEqual([{ type: 'buy', symbol: 'EUNL.DE', name: 'iShares Core MSCI World', date: '2026-10-01', quantity: 10, price: 100.1 }]);
    await waitFor(() => expect(router.state.location.pathname).toBe('/portfolio'));
  });

  it('nimmt ein ZIP an und bucht einen Verkauf, dessen Kauf in einer anderen Datei liegt', async () => {
    const trade = (key: string, type: string, date: string, status: string) => ({
      key, type, isin: 'DE0007164600', name: 'SAP', date, quantity: 5, quote: 100, fees: 0, price: 100,
      symbol: 'SAP.DE', asset_name: 'SAP SE', asset_id: 3, status,
    });
    server.use(http.post('/api/v1/me/import/depot/preview', async ({ request }) => {
      const sale = (await request.text()).includes('verkauf');
      return HttpResponse.json({
        is_trade_statement: true, note: null, sent_text: 'ABRECHNUNG',
        rows: [sale ? trade('v', 'sell', '2025-06-02', 'insufficient') : trade('k', 'buy', '2025-01-02', 'new')],
      });
    }));
    const packed = zipSync({
      'Verkauf.pdf': new Uint8Array(strToU8('verkauf')), 'Kauf.pdf': new Uint8Array(strToU8('kauf')),
    });
    renderApp('/portfolio/import');
    const user = userEvent.setup();
    await user.upload(await screen.findByLabelText('Dateien wählen'), new File([packed.slice()], 'hvb.zip', { type: 'application/zip' }));

    const preview = await screen.findByRole('region', { name: 'Vorschau' });
    await waitFor(() => expect(within(preview).getByRole('button', { name: '2 Ausführungen buchen' })).toBeEnabled());
    expect(preview).not.toHaveTextContent('zu wenig Stück');
    await user.click(within(preview).getByRole('button', { name: '2 Ausführungen buchen' }));
    await waitFor(() => expect(sent.depotImport).toHaveLength(2));
  });

  it('liest einen Krypto-Export als CSV und fragt bei unbekannten Spalten nach', async () => {
    renderApp('/portfolio/import');
    const user = userEvent.setup();
    const csv = new File(['Wann;Was;Coin;Stk;EUR\n'], 'bison.csv', { type: 'text/csv' });
    await user.upload(await screen.findByLabelText('Dateien wählen'), csv);

    const files = await screen.findByRole('region', { name: 'Dateien' });
    expect(await within(files).findByText(/Die Spalten wurden nicht erkannt/)).toBeInTheDocument();
    for (const [label, column] of [['Datum', 'Wann'], ['Art (Kauf/Verkauf)', 'Was'], ['Kryptowährung', 'Coin'], ['Menge', 'Stk'], ['Betrag in Euro', 'EUR']]) {
      await user.selectOptions(within(files).getByLabelText(label), column);
    }
    await user.click(within(files).getByRole('button', { name: 'Vorschau laden' }));

    await waitFor(() => expect(files).toHaveTextContent('bison.csv1 Ausführung · 1 übersprungen (z. B. Ein- und Auszahlungen, Dividenden)'));
    expect(sent.cryptoMapping).toEqual({ columns: { date: 0, type: 1, asset: 2, quantity: 3, total: 4 } });
    expect(screen.getByRole('region', { name: 'Vorschau' })).toHaveTextContent('KaufBTC EUR');
  });
});
