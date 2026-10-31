// Kontraste der Design-Tokens nach WCAG 2.2: Text mindestens 4,5:1, Grafik und große Zahlen 3:1.
// Liest tokens.css direkt, damit eine Farbänderung ohne Prüfung nicht durchrutscht.
import { describe, expect, it } from 'vitest';
import css from './tokens.css?raw';

function block(selector: string) {
  const start = css.indexOf(`${selector} {`);
  if (start < 0) throw new Error(`Block fehlt: ${selector}`);
  const body = css.slice(start, css.indexOf('}', start));
  return Object.fromEntries([...body.matchAll(/--([\w-]+):\s*(#[0-9a-f]{6})/gi)].map((m) => [m[1], m[2]]));
}

const light = block(':root');
const dark = { ...light, ...block(':root[data-theme="dark"]') };
const themes = {
  hell: { home: light, portfolio: { ...light, ...block(':root[data-page="portfolio"]') }, budget: { ...light, ...block(':root[data-page="budget"]') } },
  dunkel: {
    home: dark,
    portfolio: { ...dark, ...block(':root[data-theme="dark"][data-page="portfolio"]') },
    budget: { ...dark, ...block(':root[data-theme="dark"][data-page="budget"]') },
  },
};

function luminance(hex: string) {
  const [r, g, b] = [1, 3, 5].map((i) => {
    const c = parseInt(hex.slice(i, i + 2), 16) / 255;
    return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

function contrast(a: string, b: string) {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
}

// [Vordergrund, Hintergründe, Mindestwert]
const TEXT: [string, string[], number][] = [
  ['text', ['ground', 'surface', 'raised'], 4.5],
  ['muted', ['ground', 'surface', 'raised'], 4.5],
  ['faint', ['ground', 'surface'], 4.5],
  ['positive', ['ground', 'surface'], 4.5],
  ['negative', ['ground', 'surface'], 4.5],
  ['warning-ink', ['surface'], 4.5],
  ['primary-ink', ['primary'], 4.5],
  ['on-accent', ['accent'], 4.5],
  ['accent', ['surface'], 3],
  ['field-edge', ['surface'], 3],
];
const HERO: [string, number][] = [['hero-text', 4.5], ['hero-muted', 4.5], ['hero-pos', 4.5], ['hero-neg', 4.5], ['hero-accent', 3]];

describe('Kontraste der Tokens', () => {
  for (const [theme, pages] of Object.entries(themes)) {
    it(`${theme}: Text und Bedienelemente`, () => {
      const t = pages.home;
      const low = TEXT.flatMap(([fg, bgs, min]) =>
        bgs.map((bg) => [`${fg} auf ${bg}`, contrast(t[fg], t[bg]), min] as const).filter(([, ratio, m]) => ratio < m));
      expect(low.map(([name, ratio]) => `${name}: ${ratio.toFixed(2)}`)).toEqual([]);
    });

    it(`${theme}: Leitkarte jeder Seite`, () => {
      const low = Object.entries(pages).flatMap(([page, t]) =>
        HERO.map(([fg, min]) => [`${page} ${fg}`, contrast(t[fg], t['hero-bg']), min] as const).filter(([, ratio, m]) => ratio < m));
      expect(low.map(([name, ratio]) => `${name}: ${ratio.toFixed(2)}`)).toEqual([]);
    });
  }
});
