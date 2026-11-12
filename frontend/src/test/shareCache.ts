// Nachbau dessen, was der Service Worker beim Teilen ablegt: je Datei eine Antwort unter /app/share/file/<n>
// im Cache "fintrack-share". Gibt den Speicher zurück, damit Tests prüfen können, ob alles abgeholt wurde.
import { vi } from 'vitest';

export function fakeShareCache(files: File[]) {
  const store = new Map<string, Response>();
  files.forEach((file, index) => store.set(`/app/share/file/${index}`, new Response(file, {
    headers: { 'Content-Type': file.type, 'X-File-Name': encodeURIComponent(file.name) },
  })));
  const cache = {
    keys: async () => [...store.keys()].map((path) => ({ url: `http://localhost${path}` })),
    match: async (key: string) => store.get(key)?.clone(),
    delete: async (key: string) => store.delete(key),
  };
  vi.stubGlobal('caches', { open: async (name: string) => (name === 'fintrack-share' ? cache : null) });
  return store;
}
