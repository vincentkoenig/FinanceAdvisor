import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { beforeEach, describe, expect, it } from 'vitest';
import { renderApp } from '../../test/renderApp';
import { server, session, testUser } from '../../test/server';

beforeEach(() => {
  session.loggedIn = false;
});

describe('Anmeldung', () => {
  it('leitet ohne Anmeldung zur Login-Seite', async () => {
    const { router } = renderApp('/');
    expect(await screen.findByRole('heading', { name: 'Anmelden' })).toBeInTheDocument();
    expect(router.state.location.pathname).toBe('/login');
  });

  it('zeigt die Meldung der API bei falschem Passwort', async () => {
    renderApp('/login');
    const user = userEvent.setup();
    await user.type(await screen.findByLabelText('E-Mail'), testUser.email);
    await user.type(screen.getByLabelText('Passwort'), 'falsch');
    await user.click(screen.getByRole('button', { name: 'Anmelden' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('E-Mail oder Passwort ist falsch');
    expect(screen.getByLabelText('Passwort')).toHaveAttribute('aria-invalid', 'true');
  });

  it('verlangt beide Felder, bevor etwas gesendet wird', async () => {
    renderApp('/login');
    await userEvent.setup().click(await screen.findByRole('button', { name: 'Anmelden' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Bitte E-Mail und Passwort eingeben.');
  });

  it('meldet an und kehrt zur ursprünglich gewünschten Seite zurück', async () => {
    const { router } = renderApp('/irgendwo');
    const user = userEvent.setup();
    await user.type(await screen.findByLabelText('E-Mail'), testUser.email);
    await user.type(screen.getByLabelText('Passwort'), 'richtig');
    await user.click(screen.getByRole('button', { name: 'Anmelden' }));
    expect(await screen.findByRole('heading', { name: 'Seite nicht gefunden' })).toBeInTheDocument();
    expect(router.state.location.pathname).toBe('/irgendwo');
  });

  it('meldet über das Kontomenü ab', async () => {
    session.loggedIn = true;
    const { router } = renderApp('/');
    const user = userEvent.setup();
    expect(await screen.findByRole('heading', { name: 'Übersicht' })).toBeInTheDocument();
    expect(screen.getByText(`Angemeldet als ${testUser.email}`)).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Konto' }));
    await user.click(screen.getByRole('menuitem', { name: 'Abmelden' }));
    await waitFor(() => expect(router.state.location.pathname).toBe('/login'));
    expect(session.loggedIn).toBe(false);
  });

  it('zeigt einen Hinweis, wenn der Server nicht antwortet', async () => {
    server.use(http.get('/api/v1/me', () => HttpResponse.json({ error: 'Interner Fehler' }, { status: 500 })));
    renderApp('/');
    expect(await screen.findByRole('alert')).toHaveTextContent('Der Server ist gerade nicht erreichbar');
  });
});

describe('Design', () => {
  it('wechselt zwischen dunkel und hell und merkt es sich', async () => {
    session.loggedIn = true;
    renderApp('/');
    const user = userEvent.setup();
    await screen.findByRole('heading', { name: 'Übersicht' });
    expect(document.documentElement.dataset.theme).toBe('dark');
    await user.click(screen.getByRole('button', { name: 'Konto' }));
    await user.click(screen.getByRole('menuitem', { name: 'Helles Design' }));
    expect(document.documentElement.dataset.theme).toBe('light');
    expect(localStorage.getItem('fintrack-theme')).toBe('light');
  });
});
