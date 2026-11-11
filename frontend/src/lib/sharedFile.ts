// Teilen an FinTrack (Android): Der Service Worker legt die geteilte Datei kurz im Cache "fintrack-share" ab
// (siehe sw.template.js) und öffnet die Import-Seite mit ?shared=1. Diese holt sie hier genau einmal ab;
// danach ist sie vom Gerät wieder gelöscht.
const SHARE_CACHE = 'fintrack-share';
const SHARE_KEY = '/app/share/file';

export async function takeSharedFile(storage: CacheStorage | undefined = globalThis.caches): Promise<File | null> {
  if (!storage) return null;
  try {
    const cache = await storage.open(SHARE_CACHE);
    const response = await cache.match(SHARE_KEY);
    if (!response) return null;
    await cache.delete(SHARE_KEY);
    const name = decodeURIComponent(response.headers.get('X-File-Name') ?? 'geteilt');
    const blob = await response.blob();
    return new File([blob], name, { type: response.headers.get('Content-Type') ?? blob.type });
  } catch {
    return null;
  }
}
