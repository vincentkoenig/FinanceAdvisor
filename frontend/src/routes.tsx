// Alle Routen unter /app. Ohne Anmeldung führt jede Seite außer /login zur Anmeldung.
import { Navigate, Outlet, useLocation, useOutletContext, type RouteObject } from 'react-router';
import { useMe } from './api/auth';
import { AppStatus } from './components/AppStatus';
import { Shell, type RootContext } from './components/Shell';
import { ToastProvider } from './components/Toast';
import { LoginPage } from './features/auth/LoginPage';
import { HomePage } from './features/home/HomePage';
import { lazyPage } from './lib/lazyPage';
import { PrivacyProvider } from './lib/privacy';
import { useTheme } from './lib/theme';

// Übersicht und Anmeldung sind sofort da; die übrigen Seiten kommen beim ersten Öffnen nach
const PortfolioPage = lazyPage(() => import('./features/portfolio/PortfolioPage').then((m) => ({ default: m.PortfolioPage })));
const BudgetPage = lazyPage(() => import('./features/budget/BudgetPage').then((m) => ({ default: m.BudgetPage })));
const ChatPage = lazyPage(() => import('./features/chat/ChatPage').then((m) => ({ default: m.ChatPage })));
const AnalysePage = lazyPage(() => import('./features/analyse/AnalysePage').then((m) => ({ default: m.AnalysePage })));
const SettingsPage = lazyPage(() => import('./features/settings/SettingsPage').then((m) => ({ default: m.SettingsPage })));
const NotFoundPage = lazyPage(() => import('./features/NotFoundPage').then((m) => ({ default: m.NotFoundPage })));

function Root() {
  const { theme, toggle, setTheme } = useTheme();
  return (
    <PrivacyProvider>
      <ToastProvider>
        <Outlet context={{ theme, toggleTheme: toggle, setTheme } satisfies RootContext} />
        <AppStatus />
      </ToastProvider>
    </PrivacyProvider>
  );
}

function RequireAuth() {
  const context = useOutletContext<RootContext>();
  const { data: user, isPending, isError } = useMe();
  const location = useLocation();
  if (isPending) return <p className="center-note" role="status">Lädt …</p>;
  if (isError) return <p className="center-note" role="alert">Der Server ist gerade nicht erreichbar. Bitte lade die Seite gleich noch einmal.</p>;
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  return <Outlet context={context} />;
}

export const routes: RouteObject[] = [
  {
    element: <Root />,
    children: [
      { path: '/login', element: <LoginPage /> },
      {
        element: <RequireAuth />,
        children: [
          {
            element: <Shell />,
            children: [
              { index: true, element: <HomePage /> },
              { path: 'portfolio', element: <PortfolioPage /> },
              { path: 'budget', element: <BudgetPage /> },
              { path: 'chat', element: <ChatPage /> },
              { path: 'analyse', element: <AnalysePage /> },
              { path: 'settings', element: <SettingsPage /> },
              { path: '*', element: <NotFoundPage /> },
            ],
          },
        ],
      },
    ],
  },
];
