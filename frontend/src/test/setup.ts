import '@testing-library/jest-dom/vitest';
import { cleanup, configure } from '@testing-library/react';
import { afterAll, afterEach, beforeAll } from 'vitest';
import { resetData, sent, server } from './server';

// jsdom kennt matchMedia nicht; das Design fällt dann auf "dunkel" zurück
window.matchMedia ??= ((query: string) => ({
  matches: false, media: query, onchange: null,
  addListener: () => {}, removeListener: () => {}, addEventListener: () => {}, removeEventListener: () => {}, dispatchEvent: () => false,
})) as typeof window.matchMedia;

// Seiten werden nachgeladen; laufen alle Testdateien parallel, dauert das länger als die
// voreingestellte Sekunde, die findBy… wartet
configure({ asyncUtilTimeout: 4000 });

beforeAll(() => server.listen({ onUnhandledFrame: 'error' }));
afterEach(() => {
  cleanup();
  server.resetHandlers();
  resetData();
  for (const key of Object.keys(sent) as (keyof typeof sent)[]) delete sent[key];
  localStorage.clear();
});
afterAll(() => server.close());
