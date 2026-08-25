// service-worker.js - Minimaler Service Worker, nötig damit Chrome/Android
// die App als "installierbar" (PWA) erkennt. Bewusst ohne Offline-Caching,
// da FinanceAdvisor auf Live-Daten (Kurse, Chat) angewiesen ist - ein
// aggressiver Cache würde hier mehr schaden als nützen.

self.addEventListener('install', () => {
    self.skipWaiting()
})

self.addEventListener('activate', (event) => {
    event.waitUntil(self.clients.claim())
})

self.addEventListener('fetch', () => {
    // Bewusst leer - alle Requests gehen normal ans Netzwerk,
    // kein Offline-Fallback nötig für diese Live-Daten-App
})