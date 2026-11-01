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
    { asset_id: 1, name: 'iShares Core MSCI World', symbol: 'EUNL.DE', asset_type: 'etf', quantity: 100, avg_buy_price: 80, current_price: 100, previous_close: null as number | null, bought_at: null, status: 'owned' },
    { asset_id: 2, name: 'Bitcoin', symbol: 'BTC-EUR', asset_type: 'crypto', quantity: 0.1, avg_buy_price: 50000, current_price: 40000, previous_close: null as number | null, bought_at: null, status: 'owned' },
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
    { id: 50, name: 'Versicherungen', type: 'fixed_expense', parent_id: null },
    { id: 5, name: 'Sonstige Versicherungen', type: 'fixed_expense', parent_id: 50 },
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
  chat: [
    { role: 'user', message: 'Wie viel habe ich übrig?' },
    { role: 'assistant', message: 'Im Oktober bleiben dir **1.000 €**.\n\n- Einnahmen: 3.000 €\n- Ausgaben: 2.000 €' },
  ] as { role: 'user' | 'assistant'; message: string }[],
  analyses: [
    { id: 2, total_value: 14000, risk_assessment: 'Mittleres Risiko durch den Bitcoin-Anteil.', diversification_score: 5, summary: 'Das Depot ist breit über einen Welt-ETF gestreut.', recommendations: ['Krypto-Anteil im Blick behalten', 'Notgroschen prüfen'], created_at: '30.10.2026 08:00' },
    { id: 1, total_value: 12000, risk_assessment: 'Hohes Risiko.', diversification_score: 3, summary: 'Ältere Einschätzung.', recommendations: [], created_at: '01.09.2026 10:30' },
  ],
  // Fristen wie vom Server berechnet, Stand 30.10.2026
  contracts: [
    contract({ id: 51, name: 'Haftpflicht', provider: 'Beispiel Versicherung', category: 'insurance', amount: 60, interval: 'yearly', start_date: '2024-01-01', cancel_by: '2026-11-30', cancel_effective: '2026-12-31', next_term_end: '2026-12-31', days_to_cancel: 31 }),
    contract({ id: 52, name: 'Handy', category: 'telecom', amount: 19.99, interval: 'monthly', start_date: '2025-03-15', min_term_months: 24, renewal_months: 1, notice_value: 1, cancel_by: '2027-02-14', cancel_effective: '2027-03-14', next_term_end: '2027-03-14', days_to_cancel: 107, min_term_end: '2027-03-14' }),
    contract({ id: 54, name: 'Streaming', category: 'subscription', amount: 13.99, interval: 'monthly', start_date: '2022-05-03', renewal_months: 1, notice_value: 0, notice_unit: 'days', cancel_by: '2026-11-02', cancel_effective: '2026-11-02', next_term_end: '2026-11-02', days_to_cancel: 3 }),
    contract({ id: 53, name: 'Fitnessstudio', category: 'fitness', amount: 29.9, interval: 'monthly', start_date: '2025-01-01', renewal_months: 1, notice_value: 1, status: 'cancelled', cancelled_at: '2026-10-01', end_date: '2026-12-31', ends_on: '2026-12-31' }),
  ] as Contract[],
  contractSuggestions: [] as { key: string; name: string; amount: number; interval: string; first_date: string; last_date: string; count: number; category_id: number; category_name: string; kind: string }[],
  insight: { content: 'Dein Depot hat diese Woche 1,4 % zugelegt.', created_at: '2026-10-30 07:00' } as { content: string | null; created_at?: string },
});

const PER_YEAR: Record<string, number> = { monthly: 12, quarterly: 4, half_yearly: 2, yearly: 1 };

type Contract = {
  id: number; name: string; provider: string | null; category: string; contract_number: string | null;
  amount: number; interval: string; start_date: string; min_term_months: number | null; renewal_months: number | null;
  notice_value: number; notice_unit: string; notes: string | null; cancelled_at: string | null; end_date: string | null;
  min_term_end: string | null; booking: { id: number; amount: number; category_name: string | null; end_date: string | null } | null;
  status: string; next_term_end: string | null; cancel_by: string | null; cancel_effective: string | null;
  days_to_cancel: number | null; ends_on: string | null; yearly_cost: number; monthly_cost: number;
};

// Vertrag mit üblichen Werten; Kosten aus Beitrag und Zahlweise
function contract(fields: Partial<Contract> & Pick<Contract, 'id' | 'name' | 'category' | 'amount' | 'interval' | 'start_date'>): Contract {
  const yearly = Math.round(fields.amount * PER_YEAR[fields.interval] * 100) / 100;
  return {
    provider: null, contract_number: null, min_term_months: null, renewal_months: 12, notice_value: 3, notice_unit: 'months',
    notes: null, cancelled_at: null, end_date: null, status: 'active', next_term_end: null, cancel_by: null,
    cancel_effective: null, days_to_cancel: null, ends_on: null, min_term_end: null, booking: null, yearly_cost: yearly, monthly_cost: Math.round((yearly / 12) * 100) / 100,
    ...fields,
  };
}

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
export const sent: { settings?: unknown; import?: unknown; buy?: unknown; sell?: unknown; plan?: unknown; asset?: unknown; booking?: unknown; chat?: unknown; contract?: unknown; cancel?: unknown; link?: unknown; bankImport?: unknown; mapping?: unknown; depotImport?: unknown; cryptoMapping?: unknown } = {};

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

  http.get('/api/v1/me/chat/history', () => HttpResponse.json(data.chat)),
  http.delete('/api/v1/me/chat/history', () => {
    const deleted = data.chat.length;
    data.chat = [];
    return HttpResponse.json({ deleted });
  }),
  http.post('/api/v1/me/chat', async ({ request }) => {
    const { message } = (await request.json()) as { message: string };
    sent.chat = message;
    return HttpResponse.json({ reply: `Antwort auf: ${message}` });
  }),
  http.get('/api/v1/me/analyses', () => HttpResponse.json(data.analyses)),
  http.post('/api/v1/me/analyses', () => {
    data.analyses.unshift({ id: 3, total_value: 14000, risk_assessment: 'Neu bewertet.', diversification_score: 6, summary: 'Frische Analyse.', recommendations: ['Weiter so'], created_at: '31.10.2026 09:00' });
    return HttpResponse.json({ disclaimer: 'Keine Anlageberatung' });
  }),

  http.get('/api/v1/me/contracts/suggestions', () => HttpResponse.json(data.contractSuggestions)),
  http.get('/api/v1/me/contracts', () => {
    const yearly = data.contracts.filter((c) => c.status !== 'ended').reduce((sum, c) => sum + c.yearly_cost, 0);
    return HttpResponse.json({ contracts: data.contracts, yearly_total: Math.round(yearly * 100) / 100, monthly_total: Math.round((yearly / 12) * 100) / 100 });
  }),
  http.post('/api/v1/me/contracts', async ({ request }) => {
    const body = (await request.json()) as Omit<Contract, 'id'>;
    sent.contract = body;
    // Ein neuer Vertrag ist im Test immer zum 31.12.2027 kündbar; eine Mindestlaufzeit endet dann
    const saved = contract({ ...body, id: nextId++, cancel_by: '2027-09-30', cancel_effective: '2027-12-31', days_to_cancel: 335, min_term_end: body.min_term_months ? '2027-12-31' : null });
    data.contracts.push(saved);
    return HttpResponse.json({ message: 'Vertrag angelegt', contract: saved }, { status: 201 });
  }),
  http.put('/api/v1/me/contracts/:id', async ({ params, request }) => {
    const body = (await request.json()) as Omit<Contract, 'id'>;
    sent.contract = body;
    const index = data.contracts.findIndex((c) => c.id === Number(params.id));
    data.contracts[index] = contract({ ...data.contracts[index], ...body, id: Number(params.id) });
    return HttpResponse.json({ message: 'Vertrag gespeichert', contract: data.contracts[index] });
  }),
  http.post('/api/v1/me/contracts/:id/cancel', async ({ params, request }) => {
    const { end_date } = (await request.json()) as { end_date: string };
    sent.cancel = { id: Number(params.id), end_date };
    const c = data.contracts.find((x) => x.id === Number(params.id))!;
    Object.assign(c, { status: 'cancelled', cancelled_at: '2026-10-30', end_date, ends_on: end_date, cancel_by: null, cancel_effective: null, days_to_cancel: null });
    return HttpResponse.json({ message: 'Vertrag gekündigt', contract: c });
  }),
  http.delete('/api/v1/me/contracts/:id/cancel', ({ params }) => {
    const c = data.contracts.find((x) => x.id === Number(params.id))!;
    Object.assign(c, { status: 'active', cancelled_at: null, end_date: null, ends_on: null, cancel_by: '2026-11-30', cancel_effective: '2026-12-31', days_to_cancel: 31 });
    return HttpResponse.json({ message: 'Kündigung zurückgenommen', contract: c });
  }),
  http.post('/api/v1/me/contracts/:id/booking', async ({ params, request }) => {
    const body = (await request.json()) as { category_id?: number; transaction_id?: number };
    sent.link = { id: Number(params.id), ...body };
    const c = data.contracts.find((x) => x.id === Number(params.id))!;
    let t = data.transactions.find((x) => x.id === body.transaction_id);
    if (body.category_id !== undefined) {
      const category = data.categories.find((x) => x.id === body.category_id)!;
      t = { id: nextId++, amount: c.monthly_cost, description: c.name, date: '2026-10-01', end_date: c.ends_on, is_recurring: true,
        is_paused: false, paused_at: null, category_id: category.id, category_name: category.name, category_type: category.type };
      data.transactions.push(t);
    }
    c.booking = { id: t!.id, amount: t!.amount, category_name: t!.category_name, end_date: t!.end_date };
    return HttpResponse.json({ message: 'Buchung verknüpft', contract: c });
  }),
  http.delete('/api/v1/me/contracts/:id/booking', ({ params }) => {
    const c = data.contracts.find((x) => x.id === Number(params.id))!;
    c.booking = null;
    return HttpResponse.json({ message: 'Verknüpfung gelöst', contract: c });
  }),
  http.delete('/api/v1/me/contracts/:id', ({ params }) => {
    data.contracts = data.contracts.filter((c) => c.id !== Number(params.id));
    return HttpResponse.json({ message: 'Vertrag gelöscht' });
  }),

  // Kontoimport: Dateien, deren erste Zeile "Tag;Wer;Wie viel" ist, haben unbekannte Spalten
  http.post('/api/v1/me/import/bank/preview', async ({ request }) => {
    const text = await request.text();
    const mapping = new URL(request.url).searchParams.get('mapping');
    sent.mapping = mapping ? JSON.parse(mapping) : undefined;
    if (text.startsWith('Tag;') && !mapping) {
      return HttpResponse.json({ error: 'Die Spalten wurden nicht erkannt. Bitte ordne sie zu.', columns: ['Tag', 'Wer', 'Wie viel'] }, { status: 400 });
    }
    const row = (key: string, date: string, amount: number, counterparty: string, extra: object = {}) => ({
      key, occurrence: 0, line: 2, date, amount, counterparty, purpose: 'Kartenzahlung', description: counterparty,
      status: 'new', covered_by: null, category_id: null, ...extra,
    });
    const rows = [
      row('a', '2026-10-02', -1200, 'Vermieter', { status: 'covered', covered_by: { id: 13, description: 'Miete', amount: 1200 } }),
      row('b', '2026-10-05', -54.9, 'REWE Markt', { category_id: 2 }),
      row('c', '2026-10-07', -3.2, 'Café Mitte'),
      row('d', '2026-10-08', -4.5, 'Café Mitte'),
      row('e', '2026-10-09', 25, 'Erstattung'),
      row('f', '2026-09-30', -9.99, 'Streaming', { status: 'duplicate' }),
    ];
    return HttpResponse.json({
      columns: ['Buchungsdatum', 'Empfänger', 'Betrag'], mapping: { date: 0, counterparty: 1, amount: 2 }, rows,
      skipped: [{ line: 9, reason: 'kein Umsatz' }], counts: { new: 4, covered: 1, duplicate: 1 },
    });
  }),
  http.post('/api/v1/me/import/bank/pdf/preview', () => HttpResponse.json({
    columns: [], mapping: {}, skipped: [], counts: { new: 2, covered: 0, duplicate: 0 }, note: null, sent_text: 'Kontoauszug [NUMMER]',
    rows: [
      { key: 'p1', occurrence: 0, line: 1, date: '2026-10-05', amount: -54.9, counterparty: 'REWE Markt', purpose: 'Kartenzahlung', description: 'REWE Markt', status: 'new', covered_by: null, category_id: 2 },
      { key: 'p2', occurrence: 0, line: 2, date: '2026-10-07', amount: -3.2, counterparty: 'Café Mitte', purpose: 'Kartenzahlung', description: 'Café Mitte', status: 'new', covered_by: null, category_id: null },
    ],
  })),
  http.post('/api/v1/me/import/bank/commit', async ({ request }) => {
    const { rows } = (await request.json()) as { rows: unknown[] };
    sent.bankImport = rows;
    return HttpResponse.json({ message: `${rows.length} Umsätze übernommen`, created: rows.length, skipped: 0 }, { status: 201 });
  }),

  // Depot-Abrechnungen: eine Datei namens "kaputt.pdf" scheitert, alle anderen liefern dieselben zwei Ausführungen
  http.post('/api/v1/me/import/depot/preview', async ({ request }) => {
    const text = await request.text();
    if (text.includes('kaputt')) return HttpResponse.json({ error: 'Die Datei ist kein lesbares PDF.' }, { status: 400 });
    const trade = (key: string, type: string, quantity: number, quote: number, fees: number, status: string) => ({
      key, type, isin: 'IE00B4L5Y983', name: 'ISHS CORE MSCI WORLD', date: '2026-10-01', quantity, quote, fees,
      price: type === 'buy' ? quote + fees / quantity : quote - fees / quantity,
      symbol: 'EUNL.DE', asset_name: 'iShares Core MSCI World', asset_id: 1, status,
    });
    return HttpResponse.json({
      is_trade_statement: true, note: null, sent_text: 'WERTPAPIERABRECHNUNG [NUMMER]',
      rows: [trade('k1', 'buy', 10, 100, 1, 'new'), trade('k2', 'sell', 5, 105, 0, 'duplicate')],
    });
  }),
  // Krypto-CSV: ohne Zuordnung unbekannte Spalten, mit Zuordnung ein Kauf
  http.post('/api/v1/me/import/crypto/preview', ({ request }) => {
    const mapping = new URL(request.url).searchParams.get('mapping');
    if (!mapping) {
      return HttpResponse.json({ error: 'Die Spalten wurden nicht erkannt. Bitte ordne sie zu.', columns: ['Wann', 'Was', 'Coin', 'Stk', 'EUR'] }, { status: 400 });
    }
    sent.cryptoMapping = JSON.parse(mapping);
    return HttpResponse.json({
      columns: ['Wann', 'Was', 'Coin', 'Stk', 'EUR'], skipped: [{ line: 3, reason: 'Einzahlung' }],
      rows: [{ key: 'c1', type: 'buy', isin: 'BTC', name: 'BTC', date: '2026-09-01', quantity: 0.01, quote: 60000, fees: 0, price: 60000,
        symbol: 'BTC-EUR', asset_name: 'BTC EUR', asset_id: null, status: 'new' }],
    });
  }),
  http.post('/api/v1/me/import/depot/commit', async ({ request }) => {
    const { trades } = (await request.json()) as { trades: unknown[] };
    sent.depotImport = trades;
    return HttpResponse.json({ message: `${trades.length} Ausführungen gebucht`, booked: trades.length, skipped: 0 }, { status: 201 });
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
