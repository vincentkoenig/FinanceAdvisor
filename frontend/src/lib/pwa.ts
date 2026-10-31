// Service Worker anmelden und melden, wenn eine neue Version bereitsteht.
// Die neue Version übernimmt erst, wenn die Person "Neu laden" wählt; so geht keine Eingabe verloren.
import { useSyncExternalStore } from 'react';

let waiting: ServiceWorker | null = null;
let reloadRequested = false;
const listeners = new Set<() => void>();

function setWaiting(worker: ServiceWorker) {
  waiting = worker;
  listeners.forEach((listener) => listener());
}

const HOUR = 60 * 60 * 1000;

export function registerServiceWorker(
  container: ServiceWorkerContainer | undefined = navigator.serviceWorker,
  reload = () => window.location.reload(),
) {
  if (!container) return Promise.resolve();
  // Nur nach "Neu laden": beim ersten Besuch übernimmt der Service Worker ebenfalls, ohne dass neu geladen werden soll
  container.addEventListener('controllerchange', () => {
    if (reloadRequested) reload();
  });
  return container.register('/app/sw.js', { scope: '/app/' }).then((registration) => {
    // Ein Update zählt nur, wenn schon eine Version läuft; sonst ist es der erste Besuch
    const offer = (worker: ServiceWorker | null) => {
      if (worker && container.controller) setWaiting(worker);
    };
    offer(registration.waiting);
    registration.addEventListener('updatefound', () => {
      const worker = registration.installing;
      worker?.addEventListener('statechange', () => {
        if (worker.state === 'installed') offer(worker);
      });
    });
    // Eine installierte App bleibt oft tagelang offen: beim Zurückkehren und stündlich nachsehen
    document.addEventListener('visibilitychange', () => {
      if (document.visibilityState === 'visible') registration.update().catch(() => {});
    });
    setInterval(() => registration.update().catch(() => {}), HOUR);
  }).catch(() => {
    // Ohne Service Worker läuft die App normal weiter, nur ohne Offline-Seite
  });
}

export function useUpdateReady() {
  return useSyncExternalStore(
    (listener) => { listeners.add(listener); return () => { listeners.delete(listener); }; },
    () => waiting !== null,
  );
}

export function applyUpdate() {
  if (!waiting) return;
  reloadRequested = true;
  waiting.postMessage('SKIP_WAITING');
}

/** Nur für Tests */
export function resetPwaState() {
  waiting = null;
  reloadRequested = false;
  listeners.clear();
}
