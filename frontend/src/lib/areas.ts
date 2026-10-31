// Wo die Bereiche der App liegen. Solange ein Bereich noch nicht im neuen Frontend ist,
// zeigt er auf die bisherige Seite (außerhalb von /app, daher ein normaler Link).
export type Area = 'home' | 'portfolio' | 'budget' | 'chat' | 'analyse' | 'settings';

export const AREAS: Record<Area, { to: string } | { href: string }> = {
  home: { to: '/' },
  portfolio: { to: '/portfolio' },
  budget: { to: '/budget' },
  chat: { to: '/chat' },
  analyse: { to: '/analyse' },
  settings: { to: '/settings' },
};
