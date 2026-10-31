import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { delay, http, HttpResponse } from 'msw';
import { beforeEach, describe, expect, it } from 'vitest';
import { renderApp } from '../../test/renderApp';
import { data, sent, server, session } from '../../test/server';

beforeEach(() => {
  session.loggedIn = true;
});

const conversation = () => screen.findByRole('region', { name: 'Unterhaltung' });

describe('Chat', () => {
  it('ist über die Navigation erreichbar', async () => {
    const { router } = renderApp('/');
    await userEvent.setup().click((await screen.findAllByRole('link', { name: /Chat/ }))[0]);
    expect(await screen.findByRole('heading', { name: 'Chat', level: 1 })).toBeInTheDocument();
    expect(router.state.location.pathname).toBe('/chat');
  });

  it('zeigt den Verlauf, Antworten mit Formatierung', async () => {
    renderApp('/chat');
    const chat = await conversation();
    expect(await within(chat).findByText('Wie viel habe ich übrig?')).toHaveClass('msg-user');
    expect(within(chat).getByText('1.000 €').tagName).toBe('STRONG');
    expect(within(chat).getAllByRole('listitem').map((li) => li.textContent)).toEqual(['Einnahmen: 3.000 €', 'Ausgaben: 2.000 €']);
  });

  it('sendet eine Frage, zeigt sie sofort und danach die Antwort', async () => {
    server.use(http.post('/api/v1/me/chat', async ({ request }) => {
      await delay(50);
      const { message } = (await request.json()) as { message: string };
      return HttpResponse.json({ reply: `Antwort auf: ${message}` });
    }));
    renderApp('/chat');
    const user = userEvent.setup();
    const field = await screen.findByLabelText('Nachricht');
    await user.type(field, 'Ist mein Bitcoin-Anteil zu hoch?');
    await user.click(screen.getByRole('button', { name: 'Senden' }));
    expect(field).toHaveValue('');
    expect(screen.getByText('Ist mein Bitcoin-Anteil zu hoch?')).toBeInTheDocument();
    expect(screen.getByRole('status', { name: 'Antwort wird geschrieben' })).toBeInTheDocument();
    expect(await screen.findByText('Antwort auf: Ist mein Bitcoin-Anteil zu hoch?')).toBeInTheDocument();
    expect(screen.queryByRole('status', { name: 'Antwort wird geschrieben' })).not.toBeInTheDocument();
  });

  it('behält die Frage, wenn die API ablehnt', async () => {
    server.use(http.post('/api/v1/me/chat', () =>
      HttpResponse.json({ error: 'Zu viele Anfragen, bitte warte kurz' }, { status: 429 })));
    renderApp('/chat');
    const user = userEvent.setup();
    await user.type(await screen.findByLabelText('Nachricht'), 'Hallo{Enter}');
    expect(await screen.findByRole('alert')).toHaveTextContent('Zu viele Anfragen, bitte warte kurz');
    expect(screen.getByLabelText('Nachricht')).toHaveValue('Hallo');
  });

  it('schlägt in einem leeren Chat Fragen vor', async () => {
    data.chat = [];
    renderApp('/chat');
    const user = userEvent.setup();
    await user.click(await screen.findByRole('button', { name: 'Wie ist mein Depot aufgeteilt?' }));
    await waitFor(() => expect(sent.chat).toBe('Wie ist mein Depot aufgeteilt?'));
    expect(await screen.findByText('Antwort auf: Wie ist mein Depot aufgeteilt?')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Wie ist mein Depot aufgeteilt?' })).not.toBeInTheDocument();
  });

  it('sendet keine leere Nachricht', async () => {
    renderApp('/chat');
    await screen.findByLabelText('Nachricht');
    expect(screen.getByRole('button', { name: 'Senden' })).toBeDisabled();
  });
});

describe('Neuer Chat', () => {
  beforeEach(() => {
    session.loggedIn = true;
  });

  it('löscht den Verlauf nach Rückfrage und zeigt wieder die Vorschläge', async () => {
    renderApp('/chat');
    const user = userEvent.setup();
    const chat = await conversation();
    await within(chat).findByText('Wie viel habe ich übrig?');
    await user.click(screen.getByRole('button', { name: 'Neuer Chat' }));
    const dialog = screen.getByRole('dialog', { name: 'Neuen Chat beginnen?' });
    expect(dialog).toHaveTextContent('Einstellungen → Meine Daten');
    await user.click(within(dialog).getByRole('button', { name: 'Verlauf löschen' }));
    expect(await screen.findByText('Neuer Chat gestartet')).toBeInTheDocument();
    expect(within(chat).queryByText('Wie viel habe ich übrig?')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Wie viel habe ich diesen Monat übrig?' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Neuer Chat' })).not.toBeInTheDocument();
    expect(data.chat).toEqual([]);
  });

  it('lässt den Verlauf stehen, wenn abgebrochen wird', async () => {
    renderApp('/chat');
    const user = userEvent.setup();
    await within(await conversation()).findByText('Wie viel habe ich übrig?');
    await user.click(screen.getByRole('button', { name: 'Neuer Chat' }));
    await user.click(screen.getByRole('button', { name: 'Abbrechen' }));
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    expect(data.chat).toHaveLength(2);
  });
});
