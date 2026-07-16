# FinanceAdvisor 💹

A full-stack AI-powered portfolio management web application built with **Flask** and **OpenAI**. Track stocks, crypto, and precious metals, chat with an AI financial advisor, and get structured portfolio analyses — all in one app.

## Features

### 📊 Portfolio Management
- Add, buy, and sell stocks, ETFs, cryptocurrencies, and precious metals
- Assets can be added by name (e.g. "Tesla") — automatically resolved to the correct ticker via **yfinance**
- Live prices fetched on every page load via **yfinance** and **CoinGecko API**
- Automatic average buy price recalculation on new purchases
- Historical prices auto-loaded (1 year) when a new asset is added, plus a background scheduler (**APScheduler**) that periodically snapshots current prices into price history for chart continuity
- Interactive portfolio value chart with switchable time ranges (1W / 1M / YTD / 1J / Max)
- Sortable positions table (by title, buy price, position value, profit/loss)
- Allocation donut chart with total portfolio value in the center
- Privacy toggle — hide all monetary values behind asterisks with one click

### 🤖 AI Financial Advisor (Chat)
- Chat with a GPT-4o-mini powered financial advisor, available as a floating widget on every page and as a dedicated full chat page
- **Function Calling** — the AI autonomously fetches live prices (stocks, crypto, metals)
- **Web search via Tavily** — the AI searches the web for current market news and events instead of relying only on outdated training knowledge
- Adaptive response formatting (short answers for price questions, tables for comparisons, examples for explanations) — no rigid one-size-fits-all format
- Persistent chat history stored in SQLite, with a sliding window (last 20 messages) sent to the model to manage token cost and context length
- Personalized responses based on user risk profile, experience, budget, and investment horizon

### 📈 AI Portfolio Analysis
- On-demand AI analysis using **Pydantic Structured Output** (`response_format`)
- Returns structured JSON: total value, risk assessment, diversification score, summary, recommendations, and allocation
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
- **APScheduler** — background scheduler for periodic price history snapshots
- **werkzeug** — password hashing and security
- **python-dotenv** — secure API key management
- **Chart.js** — portfolio value line chart and allocation donut chart
- **marked.js** — Markdown rendering for AI chat responses

## Project Structure

```
FinanceAdvisor/
├── app.py                 # All Flask routes
├── models.py               # SQLAlchemy models + Pydantic schemas for structured output
├── api_services.py         # Live price fetching (stocks, crypto, metals, exchange rate, web search)
├── scheduler.py             # APScheduler — periodic price history snapshots
├── tools.py                 # OpenAI Function Calling tool definitions
├── requirements.txt
├── static/
│   ├── css/
│   │   ├── base.css         # Shared layout, sidebar, modal, chat widget, theme variables
│   │   ├── dashboard.css
│   │   ├── chat.css
│   │   ├── analyse.css
│   │   ├── watchlist.css
│   │   └── settings.css
│   └── js/
│       ├── dashboard.js
│       ├── chat.js
│       ├── analyse.js
│       ├── watchlist.js
│       ├── settings.js
│       ├── widget.js         # Floating chat widget
│       ├── theme.js           # Dark/Light mode toggle
│       └── logout.js
└── templates/
    ├── index.html           # Login / Register
    ├── dashboard.html       # Portfolio overview & chart
    ├── chat.html             # Full-page AI chat interface
    ├── analyse.html           # Portfolio analysis & history
    ├── watchlist.html         # Watchlist
    └── settings.html         # User profile settings
```

## API Overview

| Method | Route | Description |
|--------|-------|-------------|
| `POST` | `/register` | Register new user |
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

The SQLite database is created automatically on first run. The price scheduler starts in the background.

**5. Open in your browser**
```
http://localhost:5000
```

## What I Learned

- Building a complete multi-page Flask REST API with 20+ endpoints
- Integrating OpenAI Function Calling to let the AI autonomously fetch live data and search the web (via Tavily)
- Using Pydantic Structured Output (`response_format`) for reliable, schema-conformant JSON from LLMs
- Designing a relational SQLAlchemy database with 7 interconnected models
- Implementing secure user authentication with password hashing via `werkzeug`
- Running background tasks with APScheduler inside a Flask app context
- Fetching and reconciling live financial data across multiple APIs and currencies (yfinance, CoinGecko, USD → EUR conversion)
- Debugging currency-conversion bugs in historical price charts caused by applying live exchange rates to past prices
- Iteratively engineering a system prompt with adaptive response formatting through direct comparison against ChatGPT outputs
- Managing LLM context and token cost with a sliding window over chat history
- Combining user profile data with AI system prompts for personalized responses
- Separating concerns across multiple modules (routes, models, services, scheduler, tools) and splitting frontend CSS/JS per page for maintainability
