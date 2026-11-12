// Service Worker von FinTrack. Beim Bauen wird die Version unten eingesetzt (siehe vite.config.ts);
// eine neue Version ergibt eine neue Datei, und der Browser meldet ein Update.
//
// Regeln:
// - /api wird nie angefasst: Konto- und Depotdaten kommen immer frisch vom Server und
//   werden nie auf dem Gerät gespeichert.
// - Seiten (Navigation) zuerst aus dem Netz; ohne Netz die Offline-Seite.
// - Gehashte Dateien unter /app/assets/ ändern sich nie und kommen aus dem Cache.
// - Ein neuer Service Worker wartet, bis die App ihn bittet zu übernehmen ("Neu laden").
// - Teilen an FinTrack (Android, share_target im Manifest): Die geteilten Dateien kommen per POST an
//   /app/share. Sie liegen nur so lange im Cache "fintrack-share", bis eine Import-Seite sie abholt,
//   und werden dabei gelöscht (siehe src/lib/sharedFile.ts). Ein neues Teilen ersetzt sie.

const VERSION = '__VERSION__';
const CACHE = `fintrack-${VERSION}`;
const OFFLINE = '/app/offline.html';
const PRECACHE = [OFFLINE, '/app/icon-192.png'];
const SHARE_CACHE = 'fintrack-share';
const SHARE_PREFIX = '/app/share/file/';
const SHARE_TARGET = '/app/import/shared';

self.addEventListener('install', (event) => {
  event.waitUntil(caches.open(CACHE).then((cache) => cache.addAll(PRECACHE)));
});

self.addEventListener('activate', (event) => {
  // Caches früherer Versionen aufräumen
  event.waitUntil(
    caches.keys()
      .then((names) => Promise.all(names.filter((name) => name.startsWith('fintrack-') && name !== CACHE && name !== SHARE_CACHE).map((name) => caches.delete(name))))
      .then(() => self.clients.claim()),
  );
});

self.addEventListener('message', (event) => {
  if (event.data === 'SKIP_WAITING') self.skipWaiting();
});

// Geteilte Dateien zwischenlegen und zur Auswahl weiterleiten (Haushaltsbuch oder Depot)
async function receiveShare(request) {
  try {
    const form = await request.formData();
    const files = form.getAll('file').filter((entry) => typeof entry !== 'string');
    const cache = await caches.open(SHARE_CACHE);
    const old = await cache.keys();
    await Promise.all(old.map((key) => cache.delete(key)));
    await Promise.all(files.map((file, index) => cache.put(SHARE_PREFIX + index, new Response(file, {
      headers: { 'Content-Type': file.type || 'application/octet-stream', 'X-File-Name': encodeURIComponent(file.name || 'geteilt') },
    }))));
  } catch {
    // Ohne Dateien zeigt die Auswahl einen Hinweis, dort lassen sie sich von Hand wählen
  }
  return Response.redirect(SHARE_TARGET, 303);
}

self.addEventListener('fetch', (event) => {
  const request = event.request;
  const url = new URL(request.url);
  if (request.method === 'POST' && url.origin === self.location.origin && url.pathname === '/app/share') {
    event.respondWith(receiveShare(request));
    return;
  }
  if (request.method !== 'GET') return;
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
