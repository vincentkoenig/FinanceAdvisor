// Anmelden per Passkey (Face ID, Touch ID, Fingerabdruck). Einrichten und Verwalten steht in
// passkeySettings.ts, damit es nicht in den Einstieg der App geladen wird.
// Jeder Schritt läuft in zwei Anfragen: erst holt der Browser eine Zufallszahl (challenge) vom Server,
// dann prüft das Gerät Gesicht oder Finger und schickt die Signatur zurück.
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from './client';
import { meKey } from './auth';
import { devicePasskey } from '../lib/passkey';
import type { RequestJSON } from '../lib/webauthn';

export function usePasskeyLogin() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      const [options, { getPasskey }] = await Promise.all([
        api<RequestJSON>('/auth/passkey/options', { method: 'POST' }), import('../lib/webauthn')]);
      const credential = await getPasskey(options);
      return api<{ message: string }>('/auth/passkey/login', { method: 'POST', body: { credential } });
    },
    onSuccess: () => {
      // Hat geklappt: Auf diesem Gerät gibt es also einen Passkey
      devicePasskey.set(true);
      return client.invalidateQueries({ queryKey: meKey });
    },
  });
}
