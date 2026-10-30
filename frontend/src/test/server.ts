// Nachgebaute API für die Tests: ein Nutzer, Login mit festem Passwort, Session als Variable.
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';

export const testUser = {
  id: 1, username: null, email: 'test@fintrack.test',
  risk_profile: 'balanced', investment_experience: null, monthly_budget: null, investment_horizon: null,
};

export const session = { loggedIn: false };

export const handlers = [
  http.get('/api/v1/me', () =>
    session.loggedIn ? HttpResponse.json(testUser) : HttpResponse.json({ error: 'Bitte melde dich an' }, { status: 401 })),
  http.post('/api/v1/auth/login', async ({ request }) => {
    const body = (await request.json()) as { email: string; password: string };
    if (body.email === testUser.email && body.password === 'richtig') {
      session.loggedIn = true;
      return HttpResponse.json({ message: 'Login successful', user_id: 1 });
    }
    return HttpResponse.json({ error: 'E-Mail oder Passwort ist falsch' }, { status: 401 });
  }),
  http.post('/api/v1/auth/logout', () => {
    session.loggedIn = false;
    return HttpResponse.json({ message: 'Abgemeldet' });
  }),
];

export const server = setupServer(...handlers);
