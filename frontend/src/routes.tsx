// Alle Routen unter /app. Ohne Anmeldung führt jede Seite außer /login zur Anmeldung.
import { Navigate, Outlet, useLocation, useOutletContext, type RouteObject } from 'react-router';
import { useMe } from './api/auth';
import { Shell, type RootContext } from './components/Shell';
import { ToastProvider } from './components/Toast';
import { LoginPage } from './features/auth/LoginPage';
import { BudgetPage } from './features/budget/BudgetPage';
import { HomePage } from './features/home/HomePage';
import { NotFoundPage } from './features/NotFoundPage';
import { PortfolioPage } from './features/portfolio/PortfolioPage';
import { SettingsPage } from './features/settings/SettingsPage';
import { useTheme } from './lib/theme';

function Root() {
  const { theme, toggle, setTheme } = useTheme();
  return (
    <ToastProvider>
      <Outlet context={{ theme, toggleTheme: toggle, setTheme } satisfies RootContext} />
    </ToastProvider>
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
              { path: 'settings', element: <SettingsPage /> },
              { path: '*', element: <NotFoundPage /> },
            ],
          },
        ],
      },
    ],
  },
];
