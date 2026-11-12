import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { keyBytes, pushSupport } from '../../lib/push';
import { renderApp } from '../../test/renderApp';
import { server, session } from '../../test/server';

const ENDPOINT = 'https://push.example.com/geraet-1';

// Nachgebaute Browser-Schnittstellen: Service Worker mit pushManager, Notification, PushManager
function fakeBrowser({ subscribed = false, permission = 'granted' as NotificationPermission } = {}) {
  let current: { endpoint: string; toJSON: () => unknown; unsubscribe: () => Promise<boolean> } | null = null;
  const makeSubscription = () => ({
    endpoint: ENDPOINT,
    toJSON: () => ({ endpoint: ENDPOINT, keys: { p256dh: 'BPub', auth: 'geheim' } }),
    unsubscribe: vi.fn(async () => { current = null; return true; }),
  });
  if (subscribed) current = makeSubscription();
  const pushManager = {
    getSubscription: vi.fn(async () => current),
    subscribe: vi.fn(async () => { current = makeSubscription(); return current; }),
  };
  Object.defineProperty(navigator, 'serviceWorker', {
    configurable: true, value: { getRegistration: vi.fn(async () => ({ pushManager })) },
  });
  vi.stubGlobal('PushManager', function PushManager() {});
  vi.stubGlobal('Notification', { permission, requestPermission: vi.fn(async () => permission) });
  return pushManager;
}

function serverWithPush(device: Record<string, boolean> | null = null) {
  const sent: Record<string, unknown> = {};
  let stored = device;
  server.use(
    http.get('/api/v1/me/push', () => HttpResponse.json({ available: true, public_key: 'BAAA' })),
    http.post('/api/v1/me/push/devices', async ({ request }) => {
      sent.subscribe = await request.json();
      stored = { deadlines: true, savings_plan: true, daily_update: true, price_moves: true, watchlist: true };
      return HttpResponse.json(stored);
    }),
    http.post('/api/v1/me/push/devices/current', async ({ request }) => {
      const body = (await request.json()) as Record<string, unknown>;
      if (!stored) return HttpResponse.json({ error: 'Dieses Gerät ist nicht angemeldet' }, { status: 404 });
      const change = Object.fromEntries(Object.entries(body).filter(([key]) => key !== 'endpoint'));
      stored = { ...stored, ...(change as Record<string, boolean>) };
      return HttpResponse.json(stored);
    }),
    http.post('/api/v1/me/push/devices/remove', async ({ request }) => {
      sent.remove = await request.json();
      stored = null;
      return HttpResponse.json({ message: 'Gerät abgemeldet' });
    }),
    http.post('/api/v1/me/push/test', () => HttpResponse.json({ message: 'Test-Meldung verschickt' })),
  );
  return sent;
}

beforeEach(() => {
  session.loggedIn = true;
});

afterEach(() => {
  vi.unstubAllGlobals();
  delete (navigator as { serviceWorker?: unknown }).serviceWorker;
});

const section = () => screen.findByRole('region', { name: 'Benachrichtigungen' });

describe('Benachrichtigungen', () => {
  it('meldet, wenn der Browser kein Push kann', async () => {
    renderApp('/settings');
    expect(await within(await section()).findByText('Dieser Browser unterstützt keine Push-Benachrichtigungen.')).toBeInTheDocument();
  });

  it('meldet, wenn der Server Push nicht eingerichtet hat', async () => {
    fakeBrowser();
    renderApp('/settings');
    expect(await within(await section()).findByText(/auf dem Server noch nicht eingerichtet/)).toBeInTheDocument();
  });

  it('schaltet auf diesem Gerät ein, eine Art ab und wieder aus', async () => {
    const pushManager = fakeBrowser();
    const sent = serverWithPush();
    renderApp('/settings');
    const user = userEvent.setup();
    const box = await section();

    await user.click(await within(box).findByRole('button', { name: 'Einschalten' }));
    expect(await screen.findByText('Benachrichtigungen auf diesem Gerät eingeschaltet')).toBeInTheDocument();
    expect(pushManager.subscribe).toHaveBeenCalledWith(expect.objectContaining({ userVisibleOnly: true }));
    expect(sent.subscribe).toEqual({ endpoint: ENDPOINT, keys: { p256dh: 'BPub', auth: 'geheim' }, deadlines: true, savings_plan: true, daily_update: true, price_moves: true, watchlist: true });

    const daily = within(box).getByLabelText('Tages-Update');
    expect(daily).toBeChecked();
    expect(within(box).getByLabelText('Kündigungsfristen')).toBeChecked();
    expect(within(box).getByLabelText('Sparplan fällig')).toBeChecked();
    await user.click(daily);
    await waitFor(() => expect(within(box).getByLabelText('Tages-Update')).not.toBeChecked());

    await user.click(within(box).getByRole('button', { name: 'Test senden' }));
    expect(await screen.findByText('Test-Meldung verschickt')).toBeInTheDocument();

    await user.click(within(box).getByRole('button', { name: 'Ausschalten' }));
    expect(await within(box).findByRole('button', { name: 'Einschalten' })).toBeInTheDocument();
    expect(sent.remove).toEqual({ endpoint: ENDPOINT });
  });

  it('zeigt die Einstellungen eines schon angemeldeten Geräts', async () => {
    fakeBrowser({ subscribed: true });
    serverWithPush({ deadlines: true, savings_plan: false, daily_update: true });
    renderApp('/settings');
    const box = await section();
    expect(await within(box).findByLabelText('Sparplan fällig')).not.toBeChecked();
    expect(within(box).getByLabelText('Kündigungsfristen')).toBeChecked();
  });

  it('erklärt, was zu tun ist, wenn Benachrichtigungen blockiert sind', async () => {
    fakeBrowser({ permission: 'denied' });
    serverWithPush();
    renderApp('/settings');
    expect(await within(await section()).findByText(/für FinTrack blockiert/)).toBeInTheDocument();
  });
});

describe('lib/push', () => {
  it('erkennt ein iPhone ohne installierte App', () => {
    const iphone = { navigator: { userAgent: 'Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X)', platform: 'iPhone', maxTouchPoints: 5 } };
    expect(pushSupport(iphone as unknown as Window)).toBe('ios-install');
  });

  it('wandelt den öffentlichen Schlüssel in Bytes um', () => {
    expect(Array.from(keyBytes('AQID_-8'))).toEqual([1, 2, 3, 255, 239]);
  });
});
