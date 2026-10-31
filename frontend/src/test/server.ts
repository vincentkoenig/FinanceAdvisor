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
    { id: 11, amount: 3000, description: 'Gehalt', date: '2026-10-01', end_date: null, is_recurring: true, is_paused: false, paused_at: null, category_id: 1, category_name: 'Lohn', category_type: 'income' },
    { id: 12, amount: 54.9, description: 'Wocheneinkauf', date: '2026-10-28', end_date: null, is_recurring: false, is_paused: false, paused_at: null, category_id: 2, category_name: 'Lebensmittel', category_type: 'variable_expense' },
  ] as Txn[],
  categories: [
    { id: 10, name: 'Einkommen', type: 'income', parent_id: null },
    { id: 1, name: 'Lohn', type: 'income', parent_id: 10 },
    { id: 20, name: 'Lebenshaltung', type: 'variable_expense', parent_id: null },
    { id: 2, name: 'Lebensmittel', type: 'variable_expense', parent_id: 20 },
    { id: 4, name: 'Kleidung', type: 'variable_expense', parent_id: 20 },
    { id: 30, name: 'Wohnen', type: 'fixed_expense', parent_id: null },
    { id: 3, name: 'Miete', type: 'fixed_expense', parent_id: 30 },
  ] as { id: number; name: string; type: string; parent_id: number | null }[],
  trades: [
    { id: 21, asset_id: 1, asset_name: 'iShares Core MSCI World', asset_symbol: 'EUNL.DE', type: 'buy', quantity: 100, price: 80, total: 8000, date: '2026-01-02' },
  ],
  dividends: [
    { id: 31, asset_name: 'iShares Core MSCI World', asset_symbol: 'EUNL.DE', ex_dividend_date: '2026-06-12', amount_per_share: 0.4512, shares_held: 100, total_amount: 45.12 },
    { id: 32, asset_name: 'iShares Core MSCI World', asset_symbol: 'EUNL.DE', ex_dividend_date: '2025-12-10', amount_per_share: 0.4, shares_held: 100, total_amount: 40 },
  ],
  watchlist: [
    { asset_id: 3, name: 'SAP SE', symbol: 'SAP.DE', price_added: 200, current_price: 220, added_at: '01.10.2026' },
  ] as { asset_id: number; name: string; symbol: string; price_added: number | null; current_price: number | null; added_at: string }[],
  insight: { content: 'Dein Depot hat diese Woche 1,4 % zugelegt.', created_at: '2026-10-30 07:00' } as { content: string | null; created_at?: string },
});

type Txn = {
  id: number; amount: number; description: string | null; date: string; end_date: string | null;
  is_recurring: boolean; is_paused: boolean; paused_at: string | null;
  category_id: number; category_name: string | null; category_type: string | null;
};

// Wie die API: einmalige Buchungen im Monat, wiederkehrende in jedem Monat, in dem sie laufen
function inMonth(t: Txn, month: string) {
  const [y, m] = month.split('-').map(Number);
  const start = `${month}-01`;
  const end = m === 12 ? `${y + 1}-01-01` : `${y}-${String(m + 1).padStart(2, '0')}-01`;
  if (!t.is_recurring) return t.date >= start && t.date < end;
  return t.date < end && (t.end_date === null || t.end_date >= start);
}

let nextId = 100;

export let data = initialData();
export const resetData = () => { data = initialData(); };

// Letzte Anfragen mit Inhalt, damit Tests prüfen können, was gesendet wurde
export const sent: { settings?: unknown; import?: unknown; buy?: unknown; sell?: unknown; plan?: unknown; asset?: unknown; booking?: unknown } = {};

// Suchtreffer: ein bekanntes Asset und eines, das erst angelegt werden muss
export const searchResults = [
  { asset_id: 3, symbol: 'SAP.DE', name: 'SAP SE', exchange: 'XETRA', asset_type: 'stock', eur: true },
  { asset_id: null, symbol: 'NVD.DE', name: 'NVIDIA Corp', exchange: 'XETRA', asset_type: 'stock', eur: true },
];

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
  http.get('/api/v1/me/transactions', ({ request }) => {
    const month = new URL(request.url).searchParams.get('month');
    return HttpResponse.json(month ? data.transactions.filter((t) => inMonth(t, month)) : data.transactions);
  }),
  http.get('/api/v1/me/categories', () => HttpResponse.json(data.categories)),
  http.post('/api/v1/me/categories/init-defaults', () => {
    data.categories = [{ id: 40, name: 'Lebenshaltung', type: 'variable_expense', parent_id: null }, { id: 41, name: 'Lebensmittel', type: 'variable_expense', parent_id: 40 }];
    return HttpResponse.json({ message: 'Standardkategorien angelegt' }, { status: 201 });
  }),
  http.post('/api/v1/me/transactions', async ({ request }) => {
    const body = (await request.json()) as Omit<Txn, 'id' | 'is_paused' | 'paused_at' | 'category_name' | 'category_type'>;
    sent.booking = body;
    const category = data.categories.find((c) => c.id === body.category_id)!;
    data.transactions.push({ ...body, id: nextId++, is_paused: false, paused_at: null, category_name: category.name, category_type: category.type });
    return HttpResponse.json({ message: 'Buchung gespeichert' }, { status: 201 });
  }),
  http.post('/api/v1/me/transactions/:id/toggle-pause', ({ params }) => {
    const t = data.transactions.find((x) => x.id === Number(params.id))!;
    t.is_paused = !t.is_paused;
    t.paused_at = t.is_paused ? '2026-10-30' : null;
    return HttpResponse.json({ message: 'ok', is_paused: t.is_paused });
  }),
  http.delete('/api/v1/me/transactions/:id', ({ params }) => {
    data.transactions = data.transactions.filter((t) => t.id !== Number(params.id));
    return HttpResponse.json({ message: 'Buchung gelöscht' });
  }),
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

  http.get('/api/v1/me/watchlist', () => HttpResponse.json(data.watchlist)),
  http.post('/api/v1/me/watchlist', async ({ request }) => {
    const { asset_id } = (await request.json()) as { asset_id: number };
    const hit = searchResults.find((r) => (r.asset_id ?? 99) === asset_id)!;
    data.watchlist.push({ asset_id, name: hit.name, symbol: hit.symbol, price_added: 100, current_price: 100, added_at: '30.10.2026' });
    return HttpResponse.json({ message: 'Zur Watchlist hinzugefügt' }, { status: 201 });
  }),
  http.delete('/api/v1/me/watchlist/:id', ({ params }) => {
    data.watchlist = data.watchlist.filter((w) => w.asset_id !== Number(params.id));
    return HttpResponse.json({ message: 'Von der Watchlist entfernt' });
  }),
  http.get('/api/v1/assets/search', () => HttpResponse.json({ results: searchResults })),
  http.post('/api/v1/assets', async ({ request }) => {
    sent.asset = await request.json();
    return HttpResponse.json({ id: 99, name: 'NVIDIA Corp', symbol: 'NVD.DE', asset_type: 'stock' }, { status: 201 });
  }),
  http.get('/api/v1/assets/:id', ({ params }) =>
    HttpResponse.json({ id: Number(params.id), name: 'SAP SE', symbol: 'SAP.DE', asset_type: 'stock', current_price: 221.5 })),
  http.post('/api/v1/me/positions', async ({ request }) => {
    sent.buy = await request.json();
    return HttpResponse.json({ message: 'Position gespeichert' }, { status: 201 });
  }),
  http.post('/api/v1/me/positions/:id/sell', async ({ request, params }) => {
    sent.sell = { asset_id: Number(params.id), ...(await request.json() as object) };
    return HttpResponse.json({ message: 'Verkauf gespeichert' });
  }),
  http.post('/api/v1/me/savings-plans', async ({ request }) => {
    sent.plan = await request.json();
    return HttpResponse.json({ message: 'Sparplan erfolgreich angelegt' }, { status: 201 });
  }),
  http.delete('/api/v1/me/savings-plans/:id', ({ params }) => {
    data.savingsPlans = data.savingsPlans.filter((p) => p.id !== Number(params.id));
    return HttpResponse.json({ message: 'Sparplan gelöscht' });
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
