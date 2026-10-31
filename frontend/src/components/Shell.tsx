// Rahmen jeder Seite: Top-Leiste über einer zentrierten Spalte, auf dem Handy eine Leiste unten.
import { Suspense, useEffect, useRef, useState } from 'react';
import { Link, NavLink, Outlet, useLocation, useNavigate, useOutletContext } from 'react-router';
import { useLogout, useMe } from '../api/auth';
import { preloadPages } from '../lib/lazyPage';
import { usePrivacy } from '../lib/privacy';
import type { Theme } from '../lib/theme';
import { Icon, Mark, type IconName } from './Icon';
import { Skeleton } from './Loaded';

export type RootContext = { theme: Theme; toggleTheme: () => void; setTheme: (theme: Theme) => void };

type NavItem = { label: string; short: string; icon: IconName; to: string };

export const NAV: NavItem[] = [
  { label: 'Übersicht', short: 'Übersicht', icon: 'home', to: '/' },
  { label: 'Portfolio', short: 'Portfolio', icon: 'chart', to: '/portfolio' },
  { label: 'Haushaltsbuch', short: 'Budget', icon: 'wallet', to: '/budget' },
  { label: 'Chat', short: 'Chat', icon: 'chat', to: '/chat' },
  { label: 'Analyse', short: 'Analyse', icon: 'chart', to: '/analyse' },
];

const TITLES: Record<string, string> = { settings: 'Einstellungen' };

/** Titel des Browser-Tabs zur Seite, z. B. "Portfolio · FinTrack" */
export function pageTitle(pathname: string) {
  const page = pathname.split('/')[1] ?? '';
  const name = TITLES[page] ?? NAV.find((item) => item.to === `/${page}`)?.label ?? 'Seite nicht gefunden';
  return `${name} · FinTrack`;
}

function NavEntry({ item, compact }: { item: NavItem; compact?: boolean }) {
  const content = compact ? <><Icon name={item.icon} size={22} />{item.short}</> : item.label;
  return <NavLink to={item.to} end>{content}</NavLink>;
}

function initials(email: string) {
  return email.slice(0, 2).toUpperCase();
}

export function Shell() {
  const context = useOutletContext<RootContext>();
  const { theme, toggleTheme } = context;
  const { data: user } = useMe();
  const { hidden, setHidden } = usePrivacy();
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
    document.title = pageTitle(location.pathname);
  }, [location.pathname]);

  // Nach einem Seitenwechsel steht der Fokus auf der Überschrift, damit Screenreader und Tastatur
  // auf der neuen Seite oben beginnen. Beim ersten Laden nicht, da beginnt der Browser selbst oben.
  const shownPath = useRef(location.pathname);
  useEffect(() => {
    if (shownPath.current === location.pathname) return;
    shownPath.current = location.pathname;
    const main = document.getElementById('main');
    const focusHeading = () => {
      const heading = main?.querySelector<HTMLElement>('h1');
      if (!heading) return false;
      heading.tabIndex = -1;
      heading.focus({ preventScroll: true });
      return true;
    };
    // Eine nachgeladene Seite hat ihre Überschrift erst etwas später
    if (focusHeading() || !main) return;
    const observer = new MutationObserver(() => focusHeading() && observer.disconnect());
    observer.observe(main, { childList: true, subtree: true });
    return () => observer.disconnect();
  }, [location.pathname]);

  useEffect(() => preloadPages(), []);

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
      <a className="skip-link" href="#main" onClick={(event) => {
        event.preventDefault();
        document.getElementById('main')?.focus();
      }}>Zum Inhalt springen</a>
      <header className={`topbar${scrolled ? ' scrolled' : ''}`}>
        <div className="topbar-inner">
          <NavLink className="mark" to="/" aria-label="FinTrack, Übersicht"><Mark /><span>FinTrack</span></NavLink>
          <nav className="toplinks" aria-label="Hauptnavigation">
            {NAV.map((item) => <NavEntry key={item.label} item={item} />)}
          </nav>
          <div className="top-actions">
            <button className="icon-btn" aria-pressed={hidden} onClick={() => setHidden(!hidden)}
              aria-label="Beträge verbergen" title={hidden ? 'Beträge zeigen' : 'Beträge verbergen'}>
              <Icon name={hidden ? 'eyeOff' : 'eye'} size={20} />
            </button>
            <button className="avatar" aria-haspopup="menu" aria-expanded={menuOpen} aria-label="Konto"
              onClick={() => setMenuOpen(!menuOpen)}>
              {user ? initials(user.email) : ''}
            </button>
            {menuOpen && (
              <div className="menu" role="menu">
                <div className="menu-head">{user?.email}</div>
                <Link to="/settings" role="menuitem"><Icon name="gear" size={16} />Einstellungen</Link>
                <button role="menuitem" onClick={toggleTheme}><Icon name={theme === 'dark' ? 'sun' : 'moon'} size={16} />{themeLabel}</button>
                <div className="menu-sep" />
                <button role="menuitem" onClick={signOut} disabled={logout.isPending}><Icon name="logout" size={16} />Abmelden</button>
              </div>
            )}
          </div>
        </div>
      </header>

      <main className="canvas" id="main" tabIndex={-1}>
        <Suspense fallback={<Skeleton />}>
          <Outlet context={context} />
        </Suspense>
      </main>

      <nav className="bottom-nav" aria-label="Navigation unten">
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
              <Link to="/analyse" className="row"><Icon name="chart" /><span className="grow">Analyse</span><Icon name="right" size={16} /></Link>
              <Link className="row" to="/settings"><Icon name="gear" /><span className="grow">Einstellungen</span><Icon name="right" size={16} /></Link>
              <button className="row" onClick={toggleTheme}><Icon name={theme === 'dark' ? 'sun' : 'moon'} /><span className="grow">{themeLabel}</span></button>
              <button className="row" onClick={signOut} disabled={logout.isPending}><Icon name="logout" /><span className="grow">Abmelden</span></button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
