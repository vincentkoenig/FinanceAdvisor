import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it } from 'vitest';
import { renderApp } from '../../test/renderApp';
import { sent, session } from '../../test/server';

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
    await user.upload(await screen.findByLabelText('PDFs wählen'), [pdf('kauf.pdf'), pdf('kaputt.pdf', 'kaputt')]);

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
});
