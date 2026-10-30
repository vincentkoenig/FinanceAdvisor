// Dunkel oder hell, pro Gerät gespeichert. Ohne Wahl gilt die Einstellung des Systems.
import { useCallback, useEffect, useState } from 'react';

export type Theme = 'dark' | 'light';
const KEY = 'fintrack-theme';

function initialTheme(): Theme {
  try {
    const saved = localStorage.getItem(KEY);
    if (saved === 'dark' || saved === 'light') return saved;
  } catch {
    // Speicher gesperrt (z. B. privates Fenster): Systemeinstellung nehmen
  }
  return window.matchMedia?.('(prefers-color-scheme: light)').matches ? 'light' : 'dark';
}

export function useTheme() {
  const [theme, setTheme] = useState<Theme>(initialTheme);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    const ground = getComputedStyle(document.documentElement).getPropertyValue('--ground').trim();
    document.querySelector('meta[name="theme-color"]')?.setAttribute('content', ground);
  }, [theme]);

  const choose = useCallback((next: Theme) => {
    setTheme(next);
    try {
      localStorage.setItem(KEY, next);
    } catch {
      // nicht speicherbar, gilt dann nur bis zum Neuladen
    }
  }, []);

  const toggle = useCallback(() => choose(theme === 'dark' ? 'light' : 'dark'), [choose, theme]);

  return { theme, toggle, setTheme: choose };
}
