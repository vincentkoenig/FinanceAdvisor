// Dauerhafte Hinweise am unteren Rand: ohne Netz und wenn eine neue Version bereitsteht.
// Offline zeigt die App nur den Hinweis; Daten werden bewusst nicht auf dem Gerät gespeichert.
import { useSyncExternalStore } from 'react';
import { applyUpdate, useUpdateReady } from '../lib/pwa';

function subscribeOnline(listener: () => void) {
  window.addEventListener('online', listener);
  window.addEventListener('offline', listener);
  return () => {
    window.removeEventListener('online', listener);
    window.removeEventListener('offline', listener);
  };
}

export function useOnline() {
  return useSyncExternalStore(subscribeOnline, () => navigator.onLine);
}

export function AppStatus() {
  const online = useOnline();
  const updateReady = useUpdateReady();
  if (online && !updateReady) return null;
  return (
    <div className="app-notes">
      {!online && (
        <div className="app-note app-note-offline" role="status">
          Du bist offline. Neue Zahlen und Änderungen gehen erst wieder mit Verbindung.
        </div>
      )}
      {updateReady && (
        <div className="app-note" role="status">
          <span>Eine neue Version von FinTrack ist da.</span>
          <button className="btn btn-sm btn-primary" onClick={applyUpdate}>Neu laden</button>
        </div>
      )}
    </div>
  );
}
