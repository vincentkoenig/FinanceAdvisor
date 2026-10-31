// Automatische Barrierefreiheits-Prüfung (axe) für jede Seite. Kontraste prüft axe in jsdom nicht,
// die stehen in styles/contrast.test.ts.
import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import axe from 'axe-core';
import { beforeEach, describe, expect, it } from 'vitest';
import { renderApp } from './renderApp';
import { session } from './server';

async function violations() {
  const result = await axe.run(document.body, { rules: { 'color-contrast': { enabled: false } } });
  return result.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(' ')).join(', ')}`);
}

const PAGES = [
  ['/', 'Übersicht'],
  ['/portfolio', 'Portfolio'],
  ['/budget', 'Haushaltsbuch'],
  ['/chat', 'Chat'],
  ['/analyse', 'Analyse'],
  ['/settings', 'Einstellungen'],
] as const;

describe('Barrierefreiheit', () => {
  beforeEach(() => {
    session.loggedIn = true;
  });

  it.each(PAGES)('%s hat keine axe-Verstöße', async (path, title) => {
    renderApp(path);
    await screen.findByRole('heading', { name: title, level: 1 });
    // Daten abwarten, damit auch der geladene Inhalt geprüft wird
    await screen.findAllByRole('region');
    await new Promise((resolve) => setTimeout(resolve, 50));
    expect(await violations()).toEqual([]);
  });

  it('Anmeldung hat keine axe-Verstöße', async () => {
    session.loggedIn = false;
    renderApp('/login');
    await screen.findByLabelText('Passwort');
    expect(await violations()).toEqual([]);
  });

  it('setzt den Seitentitel und den Fokus auf die Überschrift nach einem Seitenwechsel', async () => {
    renderApp('/');
    const user = userEvent.setup();
    await screen.findByRole('heading', { name: 'Übersicht', level: 1 });
    expect(document.title).toBe('Übersicht · FinTrack');
    const nav = screen.getByRole('navigation', { name: 'Hauptnavigation' });
    await user.click(within(nav).getByRole('link', { name: 'Haushaltsbuch' }));
    const heading = await screen.findByRole('heading', { name: 'Haushaltsbuch', level: 1 });
    await waitFor(() => expect(heading).toHaveFocus());
    expect(document.title).toBe('Haushaltsbuch · FinTrack');
  });

  it('springt mit dem ersten Tab zum Inhalt', async () => {
    renderApp('/');
    const user = userEvent.setup();
    await screen.findByRole('heading', { name: 'Übersicht', level: 1 });
    await user.tab();
    const skip = screen.getByRole('link', { name: 'Zum Inhalt springen' });
    expect(skip).toHaveFocus();
    await user.keyboard('{Enter}');
    expect(screen.getByRole('main')).toHaveFocus();
  });
});
