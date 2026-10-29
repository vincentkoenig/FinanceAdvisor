// Rahmen jeder Seite: Top-Leiste über einer zentrierten Spalte, auf dem Handy eine Leiste unten.
// Bereiche, die noch nicht im neuen Frontend sind, verlinken auf die bisherigen Seiten.
import { useEffect, useState } from 'react';
import { NavLink, Outlet, useLocation, useNavigate, useOutletContext } from 'react-router';
import { useLogout, useMe } from '../api/auth';
import type { Theme } from '../lib/theme';
import { Icon, Mark, type IconName } from './Icon';

export type RootContext = { theme: Theme; toggleTheme: () => void };

type NavItem = { label: string; short: string; icon: IconName } & ({ to: string } | { href: string });

// "href" führt zur bisherigen Seite, bis der Bereich umgezogen ist
export const NAV: NavItem[] = [
  { label: 'Übersicht', short: 'Übersicht', icon: 'home', to: '/' },
  { label: 'Portfolio', short: 'Portfolio', icon: 'chart', href: '/portfolio-page' },
  { label: 'Haushaltsbuch', short: 'Budget', icon: 'wallet', href: '/budget-page' },
  { label: 'Chat', short: 'Chat', icon: 'chat', href: '/chat-page' },
  { label: 'Analyse', short: 'Analyse', icon: 'chart', href: '/analyse-page' },
];

function NavEntry({ item, compact }: { item: NavItem; compact?: boolean }) {
  const content = compact ? <><Icon name={item.icon} size={22} />{item.short}</> : item.label;
  if ('to' in item) return <NavLink to={item.to} end>{content}</NavLink>;
  return <a href={item.href}>{content}</a>;
}

function initials(email: string) {
  return email.slice(0, 2).toUpperCase();
}

export function Shell() {
  const { theme, toggleTheme } = useOutletContext<RootContext>();
  const { data: user } = useMe();
  const logout = useLogout();
  const navigate = useNavigate();
  const location = useLocation();
  // Menüs merken sich die Seite, auf der sie geöffnet wurden: nach einem Seitenwechsel sind sie zu
  const [menuAt, setMenuAt] = useState<string | null>(null);
  const [moreAt, setMoreAt] = useState<string | null>(null);
  const menuOpen = menuAt === location.pathname;
  const moreOpen = moreAt === location.pathname;
  const setMenuOpen = (open: boolean) => setMenuAt(open ? location.pathname : null);
  const setMoreOpen = (open: boolean) => setMoreAt(open ? location.pathname : null);
  const [scrolled, setScrolled] = useState(false);

  // Seite am Wurzelelement, damit die Leitkarte den Grünton der Seite bekommt
  useEffect(() => {
    const page = location.pathname.split('/')[1] || 'home';
    document.documentElement.dataset.page = page;
  }, [location.pathname]);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 4);
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  useEffect(() => {
    if (!menuOpen && !moreOpen) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') { setMenuAt(null); setMoreAt(null); }
    };
    // Klick außerhalb des Kontomenüs schließt es
    const onPointer = (event: PointerEvent) => {
      if (!(event.target as Element).closest?.('.top-actions')) setMenuAt(null);
    };
    window.addEventListener('keydown', onKey);
    window.addEventListener('pointerdown', onPointer);
    return () => {
      window.removeEventListener('keydown', onKey);
      window.removeEventListener('pointerdown', onPointer);
    };
  }, [menuOpen, moreOpen]);

  const signOut = () => logout.mutate(undefined, { onSettled: () => navigate('/login', { replace: true }) });
  const themeLabel = theme === 'dark' ? 'Helles Design' : 'Dunkles Design';

  return (
    <>
      <header className={`topbar${scrolled ? ' scrolled' : ''}`}>
        <div className="topbar-inner">
          <NavLink className="mark" to="/" aria-label="FinTrack, Übersicht"><Mark /><span>FinTrack</span></NavLink>
          <nav className="toplinks" aria-label="Hauptnavigation">
            {NAV.map((item) => <NavEntry key={item.label} item={item} />)}
          </nav>
          <div className="top-actions">
            <button className="avatar" aria-haspopup="menu" aria-expanded={menuOpen} aria-label="Konto"
              onClick={() => setMenuOpen(!menuOpen)}>
              {user ? initials(user.email) : ''}
            </button>
            {menuOpen && (
              <div className="menu" role="menu">
                <div className="menu-head">{user?.email}</div>
                <a href="/settings-page" role="menuitem"><Icon name="gear" size={16} />Einstellungen</a>
                <button role="menuitem" onClick={toggleTheme}><Icon name={theme === 'dark' ? 'sun' : 'moon'} size={16} />{themeLabel}</button>
                <div className="menu-sep" />
                <button role="menuitem" onClick={signOut} disabled={logout.isPending}><Icon name="logout" size={16} />Abmelden</button>
              </div>
            )}
          </div>
        </div>
      </header>

      <main className="canvas">
        <Outlet />
      </main>

      <nav className="bottom-nav" aria-label="Hauptnavigation">
        {NAV.slice(0, 4).map((item) => <NavEntry key={item.label} item={item} compact />)}
        <button onClick={() => setMoreOpen(true)} aria-haspopup="dialog"><Icon name="more" size={22} />Mehr</button>
      </nav>

      {moreOpen && (
        <div className="overlay" onClick={(event) => event.target === event.currentTarget && setMoreOpen(false)}>
          <div className="sheet" role="dialog" aria-modal="true" aria-labelledby="more-title">
            <div className="sheet-head">
              <h2 id="more-title">Mehr</h2>
              <button className="icon-btn" onClick={() => setMoreOpen(false)} aria-label="Schließen"><Icon name="close" /></button>
            </div>
            <div className="rows">
              <a className="row" href="/analyse-page"><Icon name="chart" /><span className="grow">Analyse</span><Icon name="right" size={16} /></a>
              <a className="row" href="/settings-page"><Icon name="gear" /><span className="grow">Einstellungen</span><Icon name="right" size={16} /></a>
              <button className="row" onClick={toggleTheme}><Icon name={theme === 'dark' ? 'sun' : 'moon'} /><span className="grow">{themeLabel}</span></button>
              <button className="row" onClick={signOut} disabled={logout.isPending}><Icon name="logout" /><span className="grow">Abmelden</span></button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
