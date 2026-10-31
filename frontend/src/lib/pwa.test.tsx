import { act, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { AppStatus } from '../components/AppStatus';
import { registerServiceWorker, resetPwaState } from './pwa';

// Nachgebauter Service Worker: Zustand, Nachrichten und statechange-Ereignis
class FakeWorker extends EventTarget {
  state = 'installing';
  postMessage = vi.fn();
  becomes(state: string) {
    this.state = state;
    this.dispatchEvent(new Event('statechange'));
  }
}

class FakeRegistration extends EventTarget {
  waiting: FakeWorker | null = null;
  installing: FakeWorker | null = null;
  update = vi.fn(() => Promise.resolve());
}

function setup({ controlled, waiting = false }: { controlled: boolean; waiting?: boolean }) {
  const registration = new FakeRegistration();
  if (waiting) registration.waiting = new FakeWorker();
  const container = Object.assign(new EventTarget(), {
    controller: controlled ? {} : null,
    register: vi.fn(() => Promise.resolve(registration)),
  });
  const reload = vi.fn();
  return { registration, container, reload, ready: registerServiceWorker(container as unknown as ServiceWorkerContainer, reload) };
}

afterEach(() => {
  resetPwaState();
  vi.restoreAllMocks();
});

describe('Service Worker', () => {
  it('meldet sich unter /app an', async () => {
    const { container, ready } = setup({ controlled: false });
    await ready;
    expect(container.register).toHaveBeenCalledWith('/app/sw.js', { scope: '/app/' });
  });

  it('bietet beim ersten Besuch kein Update an', async () => {
    const { registration, ready } = setup({ controlled: false });
    render(<AppStatus />);
    await ready;
    const worker = new FakeWorker();
    registration.installing = worker;
    act(() => {
      registration.dispatchEvent(new Event('updatefound'));
      worker.becomes('installed');
    });
    expect(screen.queryByRole('button', { name: 'Neu laden' })).not.toBeInTheDocument();
  });

  it('bietet eine neue Version an und lädt erst nach dem Klick neu', async () => {
    const { registration, container, reload, ready } = setup({ controlled: true });
    render(<AppStatus />);
    await ready;
    const worker = new FakeWorker();
    registration.installing = worker;
    act(() => {
      registration.dispatchEvent(new Event('updatefound'));
      worker.becomes('installed');
    });
    expect(screen.getByText('Eine neue Version von FinTrack ist da.')).toBeInTheDocument();
    expect(reload).not.toHaveBeenCalled();

    await userEvent.setup().click(screen.getByRole('button', { name: 'Neu laden' }));
    expect(worker.postMessage).toHaveBeenCalledWith('SKIP_WAITING');
    container.dispatchEvent(new Event('controllerchange'));
    expect(reload).toHaveBeenCalledOnce();
  });

  it('findet auch eine schon wartende Version', async () => {
    const { ready } = setup({ controlled: true, waiting: true });
    render(<AppStatus />);
    await act(() => ready);
    expect(screen.getByRole('button', { name: 'Neu laden' })).toBeInTheDocument();
  });

  it('lädt nicht neu, wenn der Service Worker von selbst übernimmt', async () => {
    const { container, reload, ready } = setup({ controlled: false });
    await ready;
    container.dispatchEvent(new Event('controllerchange'));
    expect(reload).not.toHaveBeenCalled();
  });
});

describe('Offline-Hinweis', () => {
  it('erscheint ohne Netz und verschwindet mit Verbindung', () => {
    const online = vi.spyOn(navigator, 'onLine', 'get').mockReturnValue(true);
    render(<AppStatus />);
    expect(screen.queryByText(/Du bist offline/)).not.toBeInTheDocument();
    online.mockReturnValue(false);
    act(() => { window.dispatchEvent(new Event('offline')); });
    expect(screen.getByRole('status')).toHaveTextContent('Du bist offline. Neue Zahlen und Änderungen gehen erst wieder mit Verbindung.');
    online.mockReturnValue(true);
    act(() => { window.dispatchEvent(new Event('online')); });
    expect(screen.queryByText(/Du bist offline/)).not.toBeInTheDocument();
  });
});
