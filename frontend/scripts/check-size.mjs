// Größengrenze nach dem Build (npm run size, läuft in der CI): was beim Start geladen wird, der eigene
// Code allein und jede nachgeladene Seite, jeweils komprimiert (gzip) wie beim Ausliefern.
import { readFileSync, readdirSync } from 'node:fs';
import { gzipSync } from 'node:zlib';

const LIMITS = {
  start: 130, // Einstieg + Bibliotheken + CSS, alles was die erste Seite braucht
  app: 20, // eigener Code im Einstieg, wird nach jedem Deploy neu geladen
  page: 15, // jede nachgeladene Seite
};

const kb = (bytes) => Math.round((bytes / 1024) * 10) / 10;
const gz = (file) => gzipSync(readFileSync(`dist/assets/${file}`)).length;

const html = readFileSync('dist/index.html', 'utf8');
const initial = [...html.matchAll(/\/app\/assets\/([^"]+\.(?:js|css))/g)].map((m) => m[1]);
const entry = initial.find((file) => /^index-.*\.js$/.test(file));
const lazy = readdirSync('dist/assets').filter((file) => file.endsWith('.js') && !initial.includes(file));

const checks = [
  ['Start (Einstieg, Bibliotheken, CSS)', initial.reduce((sum, file) => sum + gz(file), 0), LIMITS.start],
  [`Eigener Code (${entry})`, gz(entry), LIMITS.app],
  ...lazy.map((file) => [`Nachgeladen: ${file}`, gz(file), LIMITS.page]),
];

let failed = false;
for (const [name, size, limit] of checks) {
  const over = kb(size) > limit;
  failed ||= over;
  console.log(`${over ? 'ZU GROSS' : 'ok      '}  ${String(kb(size)).padStart(6)} kB / ${limit} kB  ${name}`);
}
if (failed) {
  console.error('\nGrößengrenze überschritten. Neue Abhängigkeit oder großer Code im Einstieg? Siehe scripts/check-size.mjs.');
  process.exit(1);
}
