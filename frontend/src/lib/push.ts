// Browser-Seite der Push-Benachrichtigungen: Kann dieses Gerät sie überhaupt, und das Abo beim
// Push-Dienst des Browsers anlegen oder löschen. Was mit dem Abo passiert, entscheidet der Server.

export type PushSupport = 'supported' | 'ios-install' | 'unsupported';

/** iPhone und iPad können Push nur in der installierten App (Home-Bildschirm), nicht in Safari. */
export function pushSupport(win: Window = window): PushSupport {
  if ('serviceWorker' in win.navigator && 'PushManager' in win && 'Notification' in win) return 'supported';
  const { userAgent, platform, maxTouchPoints } = win.navigator;
  const apple = /iPad|iPhone|iPod/.test(userAgent) || (platform === 'MacIntel' && maxTouchPoints > 1);
  return apple ? 'ios-install' : 'unsupported';
}

/** Der Service Worker von FinTrack, oder null (z. B. im Dev-Server, der keinen anmeldet). */
export async function serviceWorker() {
  return (await navigator.serviceWorker.getRegistration('/app/')) ?? null;
}

export async function currentSubscription() {
  const registration = await serviceWorker();
  return registration ? registration.pushManager.getSubscription() : null;
}

/** Öffentlicher VAPID-Schlüssel (base64url) als Bytes, wie pushManager.subscribe ihn will. */
export function keyBytes(base64url: string) {
  const base64 = (base64url + '='.repeat((4 - (base64url.length % 4)) % 4)).replace(/-/g, '+').replace(/_/g, '/');
  return Uint8Array.from(atob(base64), (char) => char.charCodeAt(0));
}

export class PushDenied extends Error {}

/** Fragt nach der Erlaubnis und legt das Abo an. */
export async function createSubscription(publicKey: string) {
  const permission = await Notification.requestPermission();
  if (permission !== 'granted') throw new PushDenied('Benachrichtigungen sind für FinTrack nicht erlaubt.');
  const registration = await serviceWorker();
  if (!registration) throw new Error('Benachrichtigungen gehen nur in der installierten oder veröffentlichten App.');
  return registration.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: keyBytes(publicKey) });
}
