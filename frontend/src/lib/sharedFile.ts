// Teilen an FinTrack (Android): Der Service Worker legt die geteilten Dateien kurz im Cache "fintrack-share" ab
// (/app/share/file/0, /1, …, siehe sw.template.js) und öffnet die Seite "Geteilte Dateien" (/import/shared).
// Dort wählt man, wohin sie gehen; die Import-Seite holt sie dann genau einmal ab und löscht sie dabei vom Gerät.
const SHARE_CACHE = 'fintrack-share';
const PREFIX = '/app/share/file/';

export type SharedInfo = { name: string; type: string };

type Storage = CacheStorage | undefined;

async function stored(storage: Storage) {
  if (!storage) return null;
  const cache = await storage.open(SHARE_CACHE);
  const keys = (await cache.keys())
    .map((request) => new URL(request.url).pathname)
    .filter((path) => path.startsWith(PREFIX))
    .sort((a, b) => Number(a.slice(PREFIX.length)) - Number(b.slice(PREFIX.length)));
  return { cache, keys };
}

const nameOf = (response: Response) => decodeURIComponent(response.headers.get('X-File-Name') ?? 'geteilt');
const typeOf = (response: Response) => response.headers.get('Content-Type') ?? '';

/** Was gerade geteilt wurde, ohne es abzuholen */
export async function peekSharedFiles(storage: Storage = globalThis.caches): Promise<SharedInfo[]> {
  try {
    const found = await stored(storage);
    if (!found) return [];
    const responses = await Promise.all(found.keys.map((key) => found.cache.match(key)));
    return responses.filter((r): r is Response => Boolean(r)).map((r) => ({ name: nameOf(r), type: typeOf(r) }));
  } catch {
    return [];
  }
}

/** Alle geteilten Dateien abholen; danach sind sie vom Gerät gelöscht */
export async function takeSharedFiles(storage: Storage = globalThis.caches): Promise<File[]> {
  try {
    const found = await stored(storage);
    if (!found) return [];
    const files: File[] = [];
    for (const key of found.keys) {
      const response = await found.cache.match(key);
      await found.cache.delete(key);
      if (response) files.push(new File([await response.blob()], nameOf(response), { type: typeOf(response) }));
    }
    return files;
  } catch {
    return [];
  }
}

/** Für den Import ins Haushaltsbuch, der eine Datei liest */
export async function takeSharedFile(storage: Storage = globalThis.caches): Promise<File | null> {
  return (await takeSharedFiles(storage))[0] ?? null;
}

export const isZipName = (info: SharedInfo) => /\.zip$/i.test(info.name) || /zip/.test(info.type);
