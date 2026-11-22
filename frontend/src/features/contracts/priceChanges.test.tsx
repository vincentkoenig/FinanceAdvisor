import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it } from 'vitest';
import { renderApp } from '../../test/renderApp';
import { sent, session } from '../../test/server';

beforeEach(() => {
  session.loggedIn = true;
});

const panel = () => screen.findByRole('region', { name: 'Neue Preise erkannt' });

describe('Neue Preise erkannt', () => {
  it('zeigt auf der Vertragsseite alle und übernimmt einen neuen Preis', async () => {
    renderApp('/contracts');
    const box = await panel();
    expect(within(box).getByText(/Netflix kostet jetzt/)).toHaveTextContent('Netflix kostet jetzt 13,99 € statt 12,99 €');
    expect(box).toHaveTextContent('+12,00 € im Jahr');
    expect(box).toHaveTextContent('Miete kostet jetzt');

    await userEvent.setup().click(within(box).getByRole('button', { name: 'Neuen Preis für Netflix übernehmen' }));

    await waitFor(() => expect(sent.priceAccept).toBe('price:contract:5:13.99'));
    expect(await screen.findByText('Netflix: neuer Preis übernommen')).toBeInTheDocument();
    await waitFor(() => expect(box).not.toHaveTextContent('Netflix kostet jetzt'));
  });

  it('zeigt im Haushaltsbuch nur wiederkehrende Buchungen und ignoriert auf Wunsch', async () => {
    renderApp('/budget');
    const box = await panel();
    expect(box).toHaveTextContent('Miete kostet jetzt');
    expect(box).not.toHaveTextContent('Netflix');

    await userEvent.setup().click(within(box).getByRole('button', { name: 'Hinweis zu Miete ignorieren' }));

    await waitFor(() => expect(sent.priceDismiss).toBe('price:booking:7:1250.00'));
    await waitFor(() => expect(screen.queryByRole('region', { name: 'Neue Preise erkannt' })).not.toBeInTheDocument());
  });
});
