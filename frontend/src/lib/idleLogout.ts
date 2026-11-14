// Automatisch abmelden: Lag FinTrack 5 Minuten oder länger im Hintergrund (App gewechselt, Tab verdeckt,
// Handy gesperrt), sind beim Zurückkommen sofort alle Daten weg und die Anmeldung erscheint.
// Der Server meldet nach 5 Minuten ohne Anfrage ohnehin ab; das hier sorgt dafür, dass die alten
// Zahlen gar nicht erst kurz sichtbar bleiben, bis die nächste Anfrage das merkt.
import { useEffect } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { meKey } from '../api/auth';
import { api } from '../api/client';

export const IDLE_LIMIT_MS = 5 * 60_000;

export function useLogoutWhenAway(now: () => number = Date.now) {
  const client = useQueryClient();

  useEffect(() => {
    let hiddenSince: number | null = document.visibilityState === 'hidden' ? now() : null;

    const onChange = () => {
      if (document.visibilityState === 'hidden') {
        hiddenSince = now();
        return;
      }
      if (hiddenSince !== null && now() - hiddenSince >= IDLE_LIMIT_MS) {
        // Erst "nicht angemeldet" setzen, dann die übrigen Daten verwerfen - so fragt nichts
        // mehr /me nach, bevor der Server die Abmeldung bekommen hat
        client.setQueryData(meKey, null);
        client.removeQueries({ predicate: (query) => query.queryKey[0] !== meKey[0] });
        api('/auth/logout', { method: 'POST' }).catch(() => {});
      }
      hiddenSince = null;
    };

    document.addEventListener('visibilitychange', onChange);
    return () => document.removeEventListener('visibilitychange', onChange);
  }, [client, now]);
}
