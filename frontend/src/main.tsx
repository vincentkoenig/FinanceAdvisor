import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { QueryClientProvider } from '@tanstack/react-query';
import { createBrowserRouter, RouterProvider } from 'react-router';
// Schriften lokal statt von Google Fonts: keine Anfrage an Dritte, funktioniert auch in der installierten App
import '@fontsource/figtree/400.css';
import '@fontsource/figtree/500.css';
import '@fontsource/figtree/600.css';
import '@fontsource/barlow-semi-condensed/500.css';
import '@fontsource/barlow-semi-condensed/600.css';
import './styles/tokens.css';
import './styles/app.css';
import { createQueryClient } from './api/auth';
import { registerServiceWorker } from './lib/pwa';
import { routes } from './routes';

const router = createBrowserRouter(routes, { basename: '/app' });

// Im Dev-Server ohne Service Worker, sonst liefert er alte Dateien aus
if (import.meta.env.PROD) window.addEventListener('load', () => registerServiceWorker());
const queryClient = createQueryClient();

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  </StrictMode>,
);
