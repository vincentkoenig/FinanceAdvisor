// Nachgebaute API für die Tests: ein Nutzer, Login mit festem Passwort, Session als Variable,
// dazu Beispieldaten für Übersicht und Portfolio. resetData() stellt vor jedem Test den Ausgangszustand her.
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';

export const testUser = {
  id: 1, username: null, email: 'test@fintrack.test',
  risk_profile: 'balanced', investment_experience: null, monthly_budget: null, investment_horizon: null,
};

export const session = { loggedIn: false };

const initialData = () => ({
  positions: [
    { asset_id: 1, name: 'iShares Core MSCI World', symbol: 'EUNL.DE', asset_type: 'etf', quantity: 100, avg_buy_price: 80, current_price: 100, bought_at: null, status: 'owned' },
    { asset_id: 2, name: 'Bitcoin', symbol: 'BTC-EUR', asset_type: 'crypto', quantity: 0.1, avg_buy_price: 50000, current_price: 40000, bought_at: null, status: 'owned' },
  ],
  summary: {
    cumulative_balance: 2000, current_month_balance: 1000, current_month_income: 3000,
    current_month_fixed: 1200, current_month_variable: 800,
  },
  history: [
    { date: '2026-10-28', value: 13600 },
    { date: '2026-10-29', value: 13800 },
  ],
  savingsPlans: [
    { id: 7, asset_id: 1, asset_name: 'iShares Core MSCI World', asset_symbol: 'EUNL.DE', amount: 200, day_of_month: 1, last_executed: '2026-09-01', is_due: true },
    { id: 8, asset_id: 2, asset_name: 'Bitcoin', asset_symbol: 'BTC-EUR', amount: 50, day_of_month: 15, last_executed: '2026-10-15', is_due: false },
  ],
  transactions: [
    { id: 11, amount: 3000, description: 'Gehalt', date: '2026-10-01', end_date: null, is_recurring: true, is_paused: false, category_id: 1, category_name: 'Lohn', category_type: 'income' },
    { id: 12, amount: 54.9, description: 'Wocheneinkauf', date: '2026-10-28', end_date: null, is_recurring: false, is_paused: false, category_id: 2, category_name: 'Lebensmittel', category_type: 'variable_expense' },
  ],
  trades: [
    { id: 21, asset_id: 1, asset_name: 'iShares Core MSCI World', asset_symbol: 'EUNL.DE', type: 'buy', quantity: 100, price: 80, total: 8000, date: '2026-01-02' },
  ],
  dividends: [
    { id: 31, asset_name: 'iShares Core MSCI World', asset_symbol: 'EUNL.DE', ex_dividend_date: '2026-06-12', amount_per_share: 0.4512, shares_held: 100, total_amount: 45.12 },
    { id: 32, asset_name: 'iShares Core MSCI World', asset_symbol: 'EUNL.DE', ex_dividend_date: '2025-12-10', amount_per_share: 0.4, shares_held: 100, total_amount: 40 },
  ],
  insight: { content: 'Dein Depot hat diese Woche 1,4 % zugelegt.', created_at: '2026-10-30 07:00' } as { content: string | null; created_at?: string },
});

export let data = initialData();
export const resetData = () => { data = initialData(); };

// Letzte Anfragen mit Inhalt, damit Tests prüfen können, was gesendet wurde
export const sent: { settings?: unknown; import?: unknown } = {};

const needsLogin = () => HttpResponse.json({ error: 'Bitte melde dich an' }, { status: 401 });

export const handlers = [
  http.get('/api/v1/me', () =>
    session.loggedIn ? HttpResponse.json(testUser) : needsLogin()),
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

  http.get('/api/v1/me/positions', () => HttpResponse.json(data.positions)),
  http.get('/api/v1/me/budget/summary', () => HttpResponse.json(data.summary)),
  http.get('/api/v1/me/portfolio/history', () => HttpResponse.json(data.history)),
  http.get('/api/v1/me/savings-plans', () => HttpResponse.json(data.savingsPlans)),
  http.get('/api/v1/me/transactions', () => HttpResponse.json(data.transactions)),
  http.get('/api/v1/me/asset-transactions', () => HttpResponse.json(data.trades)),
  http.get('/api/v1/me/dividends', () => HttpResponse.json(data.dividends)),
  http.get('/api/v1/me/insight', () => HttpResponse.json(data.insight)),
  http.post('/api/v1/me/savings-plans/:id/execute', ({ params }) => {
    const plan = data.savingsPlans.find((p) => p.id === Number(params.id));
    if (!plan) return HttpResponse.json({ error: 'Sparplan nicht gefunden' }, { status: 404 });
    plan.is_due = false;
    plan.last_executed = '2026-10-30';
    return HttpResponse.json({ message: 'Sparplan erfolgreich ausgeführt', quantity: 1.98, price: 101 });
  }),

  http.put('/api/v1/me/settings', async ({ request }) => {
    sent.settings = await request.json();
    return HttpResponse.json({ message: 'Einstellungen gespeichert' });
  }),
  http.post('/api/v1/me/import', async ({ request }) => {
    sent.import = await request.json();
    return HttpResponse.json({
      message: 'Daten importiert',
      imported: { categories: 3, transactions: 12, positions: 2, savings_plans: 1, asset_transactions: 4 },
    }, { status: 201 });
  }),
];

export const server = setupServer(...handlers);
