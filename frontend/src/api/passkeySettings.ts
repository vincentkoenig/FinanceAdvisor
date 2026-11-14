// Passkeys in den Einstellungen: auf diesem Gerät einrichten, eingerichtete Geräte auflisten und entfernen.
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from './client';
import { devicePasskey } from '../lib/passkey';
import type { CreationJSON } from '../lib/webauthn';

/** Gerätename für die Liste in den Einstellungen. */
export function deviceName(userAgent = navigator.userAgent) {
  if (/iPhone/.test(userAgent)) return 'iPhone';
  if (/iPad/.test(userAgent)) return 'iPad';
  if (/Android/.test(userAgent)) return 'Android';
  if (/Macintosh/.test(userAgent)) return 'Mac';
  if (/Windows/.test(userAgent)) return 'Windows';
  return 'Gerät';
}

export type PasskeyItem = { id: number; name: string; created_at: string | null; last_used_at: string | null };

const passkeysKey = ['passkeys'] as const;

export function usePasskeys() {
  return useQuery({ queryKey: passkeysKey, queryFn: () => api<PasskeyItem[]>('/me/passkeys') });
}

export function useAddPasskey() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      const [options, { createPasskey }] = await Promise.all([
        api<CreationJSON>('/me/passkeys/options', { method: 'POST' }), import('../lib/webauthn')]);
      const credential = await createPasskey(options);
      return api<PasskeyItem>('/me/passkeys', { method: 'POST', body: { credential, name: deviceName() } });
    },
    onSuccess: () => {
      devicePasskey.set(true);
      devicePasskey.setPreferred('passkey');
      client.invalidateQueries({ queryKey: passkeysKey });
    },
  });
}

export function useRemovePasskey() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api<{ message: string }>(`/me/passkeys/${id}`, { method: 'DELETE' }),
    onSuccess: () => client.invalidateQueries({ queryKey: passkeysKey }),
  });
}
