// Seiten, die erst beim ersten Öffnen geladen werden. Nach dem Start lädt die App sie im Leerlauf vor,
// damit der Wechsel trotzdem sofort geht.
import { lazy, type ComponentType } from 'react';

const RELOADED = 'fintrack-chunk-reload';

// Nach einem Deploy gibt es die alten Dateinamen nicht mehr. Schlägt das Nachladen fehl, lädt die
// Seite einmal neu und holt sich so die aktuelle Version.
export async function load<T>(importer: () => Promise<T>, reload = () => window.location.reload()): Promise<T> {
  try {
    const module = await importer();
    sessionStorage.removeItem(RELOADED);
    return module;
  } catch (error) {
    if (!sessionStorage.getItem(RELOADED)) {
      sessionStorage.setItem(RELOADED, '1');
      reload();
      return new Promise<T>(() => {});
    }
    throw error;
  }
}

const preloaders: (() => Promise<unknown>)[] = [];

export function lazyPage<T extends ComponentType>(importer: () => Promise<{ default: T }>) {
  // Ein gemeinsamer Ladevorgang für Vorladen und Anzeigen
  let loading: Promise<{ default: T }> | undefined;
  const get = () => (loading ??= load(importer).catch((error) => { loading = undefined; throw error; }));
  preloaders.push(get);
  return lazy(get);
}

/** Alle Seiten im Leerlauf vorladen (einmal pro Start) */
let started = false;
export function preloadPages() {
  if (started) return;
  started = true;
  const idle = window.requestIdleCallback ?? ((cb: () => void) => window.setTimeout(cb, 1500));
  idle(() => preloaders.forEach((preload) => preload().catch(() => {})));
}
