# FinanceAdvisor 💹

A full-stack AI-powered personal finance web application built with **Flask** and **OpenAI**. Track your investment portfolio, manage a household budget, chat with an AI financial advisor, and get structured portfolio analyses — all in one app, accessible to Claude Desktop via a custom MCP server.

## Features

### 🏠 Home Overview
- Consolidated dashboard showing portfolio value, cumulative cash balance, and total net worth
- Combines live portfolio valuation with the household budget's running balance

### 📊 Portfolio
- Add, buy, and sell stocks, ETFs, cryptocurrencies, and precious metals
- Assets can be added by name (e.g. "Tesla") — automatically resolved to the correct ticker via **yfinance**
- Live prices fetched on every page load via **yfinance** and **CoinGecko API**
- Automatic average buy price recalculation on new purchases
- Historical prices auto-loaded (1 year) when a new asset is added, plus a background scheduler (**APScheduler**) that snapshots current prices daily and backfills any gaps for chart continuity
- Interactive portfolio value chart with switchable time ranges (1W / 1M / YTD / 1J / Max), using forward-filled prices so weekends/holidays and newly added assets don't distort the chart
- Sortable positions table (by title, buy price, position value, profit/loss)
- Allocation donut chart with dynamically generated, unique colors per asset and total portfolio value in the center
- Privacy toggle — hide all monetary values behind asterisks with one click

### 💰 Haushaltsbuch (Household Budget)
- Track income, fixed costs, and variable expenses in a three-tier category structure (Einkommen / Fixkosten / Variable Ausgaben), each with customizable main and sub-categories
- Default category set auto-created for every new user, fully editable/deletable afterward
- One-time and recurring transactions (e.g. monthly salary or rent) with optional end dates — recurring entries are calculated on the fly per month, not duplicated in the database
- Month-by-month navigation with income/fixed/variable/balance summary cards
- Category breakdown per section with percentage share, and a donut chart visualizing expenses by category
- Full transaction list with delete functionality
- Cumulative cash balance calculated across all months since the first transaction, feeding into the Home overview

### 🤖 AI Financial Advisor (Chat)
- Chat with a GPT-4o-mini powered financial advisor, available as a floating widget on every page and as a dedicated full chat page
- **Function Calling** — the AI autonomously fetches live prices (stocks, crypto, metals) and can call multiple tools in a single turn
- **Web search via Tavily** — the AI searches the web for current market news and events instead of relying only on outdated training knowledge
- Adaptive response formatting (short answers for price questions, tables for comparisons, examples for explanations) — no rigid one-size-fits-all format
- Persistent chat history stored in SQLite, with a sliding window (last 20 messages) sent to the model to manage token cost and context length
- Personalized responses based on user risk profile, experience, budget, and investment horizon

### 📈 AI Portfolio Analysis
- On-demand AI analysis using **Pydantic Structured Output** (`response_format`)
- Returns structured JSON: risk assessment, diversification score, summary, recommendations, and allocation
- Total portfolio value is computed server-side (not left to the LLM) for numerical accuracy
- All past analyses saved and browsable from the analysis page

### 👤 User System
- Register and login with email and hashed password (`werkzeug.security`)
- Per-user settings: risk profile, investment experience, monthly budget, investment horizon
- User profile data injected into every AI system prompt for personalized advice
- Dark/Light mode toggle, persisted across pages and sessions

### 👁️ Watchlist
- Add and remove assets to a personal watchlist — separate from the portfolio, for tracking without owning
- Shows current price, price at the time it was added, absolute/percentage change, and date added
- Buy directly from the watchlist (moves the asset into the portfolio and removes it from the watchlist)

### 🔌 MCP Server
- Standalone Model Context Protocol server exposing FinanceAdvisor data to MCP-compatible clients like Claude Desktop
- Three tools: `get_portfolio_summary` (current holdings), `get_budget_status` (monthly income/expenses/balance), `add_transaction` (create a new budget entry directly from a chat conversation)
- Reuses the same SQLAlchemy models and budget calculation logic as the web app (no duplicated business logic)
- See [`mcp_server/`](./mcp_server) for setup details

### 🎨 UI / Design
- Custom "liquid glass" interface — translucent, blurred cards over a soft radial gradient background, applied consistently across every page, modal, and the chat widget
- Fully theme-aware: all glass effect colors are defined as CSS variables with separate dark and light mode values
- Toast notifications instead of browser alerts, loading spinners on all async data fetches, and client-side validation on every form

## Tech Stack

![Python](https://img.shields.io/badge/Python-3776AB?style=flat&logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-000000?style=flat&logo=flask&logoColor=white)
![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-D71F00?style=flat&logo=sqlalchemy&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-003B57?style=flat&logo=sqlite&logoColor=white)
![OpenAI](https://img.shields.io/badge/OpenAI_API-412991?style=flat&logo=openai&logoColor=white)
![HTML5](https://img.shields.io/badge/HTML5-E34F26?style=flat&logo=html5&logoColor=white)
![JavaScript](https://img.shields.io/badge/JavaScript-F7DF1E?style=flat&logo=javascript&logoColor=black)

- **Flask** — REST API backend & HTML page rendering
- **SQLAlchemy** — ORM with SQLite for all persistent data
- **OpenAI API** — GPT-4o-mini for chat (Function Calling) and portfolio analysis (Structured Output)
- **Tavily** — real-time web search for current financial news, integrated as an LLM tool
- **Pydantic** — structured output parsing for portfolio analysis
- **yfinance** — stock, ETF, and precious metal price data, historical prices, and asset search by name
- **CoinGecko API** — cryptocurrency prices
- **APScheduler** — background scheduler for daily price history snapshots and gap-filling
- **MCP (Model Context Protocol)** — standalone server exposing app data as tools to Claude Desktop
- **werkzeug** — password hashing and security
- **python-dotenv** — secure API key management
- **Chart.js** — portfolio value line chart, allocation donut, and budget expense donut
- **marked.js** — Markdown rendering for AI chat responses

## Project Structure

```
FinanceAdvisor/
├── app.py                   # All Flask routes
├── models.py                 # SQLAlchemy models + Pydantic schemas for structured output
├── budget_logic.py            # Shared household budget calculation logic (used by app.py and mcp_server)
├── api_services.py            # Live price fetching (stocks, crypto, metals, exchange rate, web search)
├── scheduler.py                # APScheduler — daily price snapshots with gap-filling
├── tools.py                    # OpenAI Function Calling tool definitions
├── requirements.txt
├── mcp_server/
│   └── server.py                # MCP server exposing portfolio/budget tools to Claude Desktop
├── docs/                        # Screenshots, demo video, misc project assets
├── static/
│   ├── css/
│   │   ├── base.css             # Shared layout, sidebar, glass effect variables, modal, chat widget
│   │   ├── home.css
│   │   ├── portfolio.css
│   │   ├── budget.css
│   │   ├── chat.css
│   │   ├── analyse.css
│   │   ├── watchlist.css
│   │   └── settings.css
│   └── js/
│       ├── home.js
│       ├── portfolio.js
│       ├── budget.js
│       ├── chat.js
│       ├── analyse.js
│       ├── watchlist.js
│       ├── settings.js
│       ├── widget.js             # Floating chat widget
│       ├── theme.js               # Dark/Light mode toggle
│       ├── toast.js               # Toast notification helper
│       ├── utils.js               # Shared helpers (e.g. dynamic color generation)
│       └── logout.js
└── templates/
    ├── index.html               # Login / Register
    ├── home.html                 # Net worth overview
    ├── portfolio.html             # Portfolio overview & chart
    ├── budget.html                 # Household budget
    ├── chat.html                   # Full-page AI chat interface
    ├── analyse.html                 # Portfolio analysis & history
    ├── watchlist.html               # Watchlist
    └── settings.html                 # User profile settings
```

## API Overview

| Method | Route | Description |
|--------|-------|-------------|
| `POST` | `/register` | Register new user (auto-creates default budget categories) |
| `POST` | `/login` | Login |
| `GET` | `/users/<id>` | Get user profile |
| `PUT` | `/users/<id>/settings` | Update investment settings |
| `GET` | `/assets/<id>` | Get asset details with live price |
| `GET` | `/assets/search` | Search asset by name or symbol, auto-creates it and loads historical prices |
| `POST` | `/assets/<id>/prices` | Manually add a historical price entry |
| `GET` | `/users/<id>/assets` | Get portfolio (live prices) |
| `POST` | `/users/<id>/assets` | Add asset to portfolio |
| `PUT` | `/users/<id>/assets/<id>/buy` | Record a buy (updates avg price) |
| `PUT` | `/users/<id>/assets/<id>/sell` | Record a sell |
| `GET` | `/users/<id>/portfolio/history` | Price history for chart |
| `POST` | `/portfolio/analyze` | AI portfolio analysis |
| `GET` | `/users/<id>/portfolio/analyses` | Get all past analyses |
| `POST` | `/chat` | AI chat with Function Calling and web search |
| `GET` | `/chat/history/<id>` | Get chat history |
| `GET/POST/DELETE` | `/users/<id>/watchlist` | Manage watchlist |
| `POST` | `/update-prices` | Manually trigger a price update |
| `GET` | `/users/<id>/categories` | Get all budget categories for a user |
| `POST` | `/users/<id>/categories` | Add a new category or subcategory |
| `DELETE` | `/categories/<id>` | Delete a category (and its subcategories) |
| `POST` | `/users/<id>/categories/init-defaults` | Retroactively create default categories for an existing user |
| `GET` | `/users/<id>/transactions` | Get transactions, optionally filtered by month (`?month=YYYY-MM`) |
| `POST` | `/users/<id>/transactions` | Add a transaction (one-time or recurring) |
| `DELETE` | `/transactions/<id>` | Delete a transaction |
| `GET` | `/users/<id>/budget/summary` | Cumulative cash balance and current month breakdown |

## Getting Started

**1. Clone the repository**
```bash
git clone https://github.com/vincentkoenig/FinanceAdvisor.git
cd FinanceAdvisor
```

**2. Install dependencies**
```bash
pip install -r requirements.txt
```

**3. Create a `.env` file**
```
OPENAI_API_KEY=your_openai_api_key
COINGECKO_API_KEY=your_coingecko_api_key
TAVILY_API_KEY=your_tavily_api_key
```
> Get your keys at [platform.openai.com](https://platform.openai.com/api-keys), [coingecko.com](https://www.coingecko.com/en/api), and [tavily.com](https://tavily.com)

**4. Run the app**
```bash
python app.py
```
Or, on Windows, double-click `start.bat` to launch the server and open it in your browser automatically.

The SQLite database is created automatically on first run inside the `instance/` folder. The price scheduler starts in the background.

**5. Open in your browser**
```
http://localhost:5000
```

**6. (Optional) Connect the MCP server to Claude Desktop**

See [`mcp_server/`](./mcp_server) for the full setup guide — in short, add an entry to your `claude_desktop_config.json` pointing to `mcp_server/server.py` using your virtual environment's Python interpreter, then restart Claude Desktop.

## What I Learned

- Building a complete multi-page Flask REST API with 30+ endpoints
- Integrating OpenAI Function Calling to let the AI autonomously fetch live data, search the web (via Tavily), and correctly handle multiple simultaneous tool calls in one turn
- Using Pydantic Structured Output (`response_format`) for reliable, schema-conformant JSON from LLMs, while keeping numerically critical values (like total portfolio value) computed server-side rather than trusting the LLM's arithmetic
- Designing a relational SQLAlchemy database with 9 interconnected models, including a two-level self-referencing category structure for the household budget
- Modeling recurring transactions (income/expenses) as single database rows that are evaluated per-month on read, instead of duplicating rows — avoiding scheduler-dependent generation entirely
- Implementing secure user authentication with password hashing via `werkzeug`
- Running background tasks with APScheduler inside a Flask app context, including gap-filling logic for missed price updates
- Fetching and reconciling live financial data across multiple APIs and currencies (yfinance, CoinGecko, USD → EUR conversion), and debugging chart artifacts caused by weekends/holidays and by applying live exchange rates to historical prices
- Iteratively engineering a system prompt with adaptive response formatting through direct comparison against ChatGPT outputs
- Managing LLM context and token cost with a sliding window over chat history
- Extracting shared business logic (`budget_logic.py`) so the same calculation is used by both the Flask web app and an independent MCP server, avoiding logic duplication
- Building and debugging a Model Context Protocol server from scratch — resolving Flask application context requirements, absolute path handling (a MCP client can launch the server from an arbitrary working directory), and virtual environment interpreter resolution for Claude Desktop
- Implementing a cohesive, theme-aware "glass" design system using CSS custom properties, `backdrop-filter`, and layered transparency across an entire multi-page application
- Separating concerns across multiple modules (routes, models, services, scheduler, tools, budget logic) and splitting frontend CSS/JS per page for maintainability
