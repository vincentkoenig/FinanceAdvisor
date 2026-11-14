import { act, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { renderApp } from '../../test/renderApp';
import { server, session } from '../../test/server';
import { biometricName, devicePasskey } from '../../lib/passkey';

// jsdom kennt kein WebAuthn: ein Gerät, das nach "Face ID" sofort signiert
const bytes = (text: string) => new TextEncoder().encode(text).buffer;
const fakeAssertion = {
  id: 'cred-1', type: 'public-key', rawId: bytes('cred-1'),
  response: { clientDataJSON: bytes('{}'), authenticatorData: bytes('auth'), signature: bytes('sig'), userHandle: bytes('1') },
};
const fakeAttestation = {
  id: 'cred-1', type: 'public-key', rawId: bytes('cred-1'),
  response: { clientDataJSON: bytes('{}'), attestationObject: bytes('att'), getTransports: () => ['internal'] },
};
const credentials = { get: vi.fn(), create: vi.fn() };
const name = biometricName();

function passkeyServer() {
  server.use(
    http.post('/api/v1/auth/passkey/options', () => HttpResponse.json({ challenge: 'Y2hhbGxlbmdl', rpId: 'localhost', userVerification: 'required' })),
    http.post('/api/v1/auth/passkey/login', () => {
      session.loggedIn = true;
      return HttpResponse.json({ message: 'Login successful', user_id: 1 });
    }),
  );
}

beforeEach(() => {
  session.loggedIn = false;
  credentials.get.mockReset();
  credentials.create.mockReset();
  vi.stubGlobal('PublicKeyCredential', function PublicKeyCredential() {});
  Object.defineProperty(navigator, 'credentials', { configurable: true, value: credentials });
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe('Anmeldung per Passkey', () => {
  it('zeigt ohne eingerichteten Passkey nur das Passwort-Formular', async () => {
    renderApp('/login');
    expect(await screen.findByLabelText('Passwort')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: `Mit ${name} anmelden` })).not.toBeInTheDocument();
    expect(credentials.get).not.toHaveBeenCalled();
  });

  it('startet die bevorzugte Methode beim Öffnen von selbst und meldet an', async () => {
    devicePasskey.set(true);
    passkeyServer();
    credentials.get.mockResolvedValue(fakeAssertion);
    const { router } = renderApp('/');
    expect(await screen.findByRole('heading', { name: 'Übersicht' })).toBeInTheDocument();
    expect(credentials.get).toHaveBeenCalledTimes(1);
    expect(router.state.location.pathname).toBe('/');
  });

  it('bietet nach Abbruch erneut den Knopf und das Passwort an', async () => {
    devicePasskey.set(true);
    passkeyServer();
    credentials.get.mockRejectedValueOnce(new DOMException('abgebrochen', 'NotAllowedError'));
    renderApp('/login');
    const user = userEvent.setup();
    const button = await screen.findByRole('button', { name: `Mit ${name} anmelden` });
    await waitFor(() => expect(button).toBeEnabled());
    // Abbrechen ist kein Fehler, der angezeigt wird
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Stattdessen mit Passwort anmelden' }));
    expect(screen.getByLabelText('Passwort')).toBeInTheDocument();
    // Der Passkey bleibt als zweiter Weg darunter
    expect(screen.getByRole('button', { name: `Mit ${name} anmelden` })).toBeInTheDocument();
  });

  it('beginnt mit dem Passwort, wenn das als bevorzugt gewählt ist', async () => {
    devicePasskey.set(true);
    devicePasskey.setPreferred('password');
    renderApp('/login');
    expect(await screen.findByLabelText('Passwort')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: `Mit ${name} anmelden` })).toBeInTheDocument();
    expect(credentials.get).not.toHaveBeenCalled();
  });

  it('zeigt eine Meldung, wenn der Server den Passkey nicht kennt', async () => {
    devicePasskey.set(true);
    server.use(
      http.post('/api/v1/auth/passkey/options', () => HttpResponse.json({ challenge: 'Y2hhbGxlbmdl' })),
      http.post('/api/v1/auth/passkey/login', () => HttpResponse.json({ error: 'Die Anmeldung per Passkey hat nicht geklappt.' }, { status: 401 })),
    );
    credentials.get.mockResolvedValue(fakeAssertion);
    renderApp('/login');
    expect(await screen.findByRole('alert')).toHaveTextContent('Die Anmeldung per Passkey hat nicht geklappt.');
  });
});

describe('Passkey einrichten', () => {
  it('richtet das Gerät in den Einstellungen ein und macht es zur bevorzugten Methode', async () => {
    session.loggedIn = true;
    let sentName = '';
    server.use(
      http.post('/api/v1/me/passkeys/options', () => HttpResponse.json({
        challenge: 'Y2hhbGxlbmdl', rp: { id: 'localhost', name: 'FinTrack' },
        user: { id: 'MQ', name: 'test@fintrack.test', displayName: 'test@fintrack.test' }, pubKeyCredParams: [],
      })),
      http.post('/api/v1/me/passkeys', async ({ request }) => {
        sentName = ((await request.json()) as { name: string }).name;
        return HttpResponse.json({ id: 1, name: sentName, created_at: '2026-11-14T20:00:00', last_used_at: null }, { status: 201 });
      }),
    );
    credentials.create.mockResolvedValue(fakeAttestation);
    renderApp('/settings');
    const user = userEvent.setup();
    await user.click(await screen.findByRole('button', { name: 'Einrichten' }));
    expect(await screen.findByRole('group', { name: 'Bevorzugte Anmeldung auf diesem Gerät' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name, pressed: true })).toBeInTheDocument();
    expect(devicePasskey.preferred()).toBe('passkey');
    expect(sentName).not.toBe('');
  });
});

describe('Automatisch abmelden', () => {
  let visibility: DocumentVisibilityState = 'visible';
  const setVisibility = (value: DocumentVisibilityState) => {
    visibility = value;
    act(() => { document.dispatchEvent(new Event('visibilitychange')); });
  };

  beforeEach(() => {
    visibility = 'visible';
    Object.defineProperty(document, 'visibilityState', { configurable: true, get: () => visibility });
  });

  it('meldet nach 5 Minuten im Hintergrund ab', async () => {
    session.loggedIn = true;
    const now = vi.spyOn(Date, 'now').mockReturnValue(1_000_000);
    const { router } = renderApp('/');
    expect(await screen.findByRole('heading', { name: 'Übersicht' })).toBeInTheDocument();

    setVisibility('hidden');
    now.mockReturnValue(1_000_000 + 5 * 60_000);
    setVisibility('visible');

    expect(await screen.findByRole('heading', { name: 'Anmelden' })).toBeInTheDocument();
    expect(router.state.location.pathname).toBe('/login');
    await waitFor(() => expect(session.loggedIn).toBe(false));
  });

  it('bleibt angemeldet nach kurzem Wechsel in eine andere App', async () => {
    session.loggedIn = true;
    const now = vi.spyOn(Date, 'now').mockReturnValue(1_000_000);
    renderApp('/');
    expect(await screen.findByRole('heading', { name: 'Übersicht' })).toBeInTheDocument();

    setVisibility('hidden');
    now.mockReturnValue(1_000_000 + 4 * 60_000);
    setVisibility('visible');

    expect(screen.getByRole('heading', { name: 'Übersicht' })).toBeInTheDocument();
    expect(session.loggedIn).toBe(true);
  });
});
