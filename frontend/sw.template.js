// Service Worker von FinTrack. Beim Bauen wird die Version unten eingesetzt (siehe vite.config.ts);
// eine neue Version ergibt eine neue Datei, und der Browser meldet ein Update.
//
// Regeln:
// - /api wird nie angefasst: Konto- und Depotdaten kommen immer frisch vom Server und
//   werden nie auf dem Gerät gespeichert.
// - Seiten (Navigation) zuerst aus dem Netz; ohne Netz die Offline-Seite.
// - Gehashte Dateien unter /app/assets/ ändern sich nie und kommen aus dem Cache.
// - Ein neuer Service Worker wartet, bis die App ihn bittet zu übernehmen ("Neu laden").

const VERSION = '__VERSION__';
const CACHE = `fintrack-${VERSION}`;
const OFFLINE = '/app/offline.html';
const PRECACHE = [OFFLINE, '/app/icon-192.png'];

self.addEventListener('install', (event) => {
  event.waitUntil(caches.open(CACHE).then((cache) => cache.addAll(PRECACHE)));
});

self.addEventListener('activate', (event) => {
  // Caches früherer Versionen aufräumen
  event.waitUntil(
    caches.keys()
      .then((names) => Promise.all(names.filter((name) => name.startsWith('fintrack-') && name !== CACHE).map((name) => caches.delete(name))))
      .then(() => self.clients.claim()),
  );
});

self.addEventListener('message', (event) => {
  if (event.data === 'SKIP_WAITING') self.skipWaiting();
});

self.addEventListener('fetch', (event) => {
  const request = event.request;
  if (request.method !== 'GET') return;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin || url.pathname.startsWith('/api/')) return;

  if (request.mode === 'navigate') {
    event.respondWith(fetch(request).catch(() => caches.match(OFFLINE)));
    return;
  }

  // Was die Offline-Seite braucht (ihr Icon), auch ohne Netz
  if (PRECACHE.includes(url.pathname)) {
    event.respondWith(fetch(request).catch(() => caches.match(request)));
    return;
  }

  if (url.pathname.startsWith('/app/assets/')) {
    event.respondWith(
      caches.open(CACHE).then((cache) => cache.match(request).then((hit) => hit || fetch(request).then((response) => {
        if (response.ok) cache.put(request, response.clone());
        return response;
      }))),
    );
  }
});
