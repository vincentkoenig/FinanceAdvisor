// Push-Benachrichtigungen: ob der Server sie anbietet, und die Anmeldung dieses Geräts.
// Ein Gerät erkennt der Server an seinem endpoint; der steht nur im Browser und geht deshalb
// immer im Body mit, nie in der URL.
import { useQuery } from '@tanstack/react-query';
import { api } from './client';

export type PushConfig = { available: boolean; public_key: string | null };
export type DeviceSettings = { deadlines: boolean; savings_plan: boolean; daily_update: boolean };

export function usePushConfig() {
  return useQuery({ queryKey: ['push-config'], queryFn: () => api<PushConfig>('/me/push') });
}

export const pushApi = {
  subscribe: (subscription: PushSubscriptionJSON, settings: DeviceSettings) =>
    api<DeviceSettings>('/me/push/devices', { method: 'POST', body: { ...subscription, ...settings } }),
  settings: (endpoint: string, change: Partial<DeviceSettings> = {}) =>
    api<DeviceSettings>('/me/push/devices/current', { method: 'POST', body: { endpoint, ...change } }),
  remove: (endpoint: string) => api<{ message: string }>('/me/push/devices/remove', { method: 'POST', body: { endpoint } }),
  test: (endpoint: string) => api<{ message: string }>('/me/push/test', { method: 'POST', body: { endpoint } }),
};
