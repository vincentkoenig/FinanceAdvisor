// Alle Routen unter /app. Ohne Anmeldung führt jede Seite außer /login zur Anmeldung.
import { Navigate, Outlet, useLocation, useOutletContext, type RouteObject } from 'react-router';
import { useMe } from './api/auth';
import { Shell, type RootContext } from './components/Shell';
import { LoginPage } from './features/auth/LoginPage';
import { HomePage } from './features/home/HomePage';
import { NotFoundPage } from './features/NotFoundPage';
import { useTheme } from './lib/theme';

function Root() {
  const { theme, toggle } = useTheme();
  return <Outlet context={{ theme, toggleTheme: toggle } satisfies RootContext} />;
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
              { path: '*', element: <NotFoundPage /> },
            ],
          },
        ],
      },
    ],
  },
];
