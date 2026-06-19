# FinanceAdvisor 💹

A full-stack AI-powered portfolio management web application built with **Flask** and **OpenAI**. Track stocks, crypto, and precious metals, chat with an AI financial advisor, and get structured portfolio analyses — all in one app.

## Features

### 📊 Portfolio Management
- Add, buy, and sell stocks, ETFs, cryptocurrencies, and precious metals
- Live price updates via **yfinance** and **CoinGecko API** — refreshed every 5 minutes by a background scheduler
- Automatic average buy price recalculation on new purchases
- Portfolio value history chart for all active assets

### 🤖 AI Financial Advisor (Chat)
- Chat with a GPT-4o-mini powered financial advisor
- **Function Calling** — the AI fetches live prices (stocks, crypto, metals) and searches the web in real time
- Persistent chat history stored in SQLite for full conversation context
- Personalized responses based on user risk profile, experience, budget, and investment horizon

### 📈 AI Portfolio Analysis
- On-demand AI analysis using **Pydantic Structured Output** (`response_format`)
- Returns structured JSON: total value, risk assessment, diversification score, summary, recommendations, and allocation
- All analyses saved to the database with timestamps

### 👤 User System
- Register and login with email and hashed password (`werkzeug.security`)
- Per-user settings: risk profile, investment experience, monthly budget, investment horizon
- User profile data injected into every AI system prompt for personalized advice

### 👁️ Watchlist
- Add and remove assets to a personal watchlist
- Separate from portfolio — for tracking without owning

## Tech Stack

![Python](https://img.shields.io/badge/Python-3776AB?style=flat&logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-000000?style=flat&logo=flask&logoColor=white)
![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-D71F00?style=flat&logo=sqlalchemy&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-003B57?style=flat&logo=sqlite&logoColor=white)
![OpenAI](https://img.shields.io/badge/OpenAI_API-412991?style=flat&logo=openai&logoColor=white)
![HTML5](https://img.shields.io/badge/HTML5-E34F26?style=flat&logo=html5&logoColor=white)

- **Flask** — REST API backend & HTML page rendering
- **SQLAlchemy** — ORM with SQLite for all persistent data
- **OpenAI API** — GPT-4o-mini for chat and portfolio analysis
- **Pydantic** — structured output parsing for portfolio analysis
- **yfinance** — stock and ETF price data and asset search
- **APScheduler** — background scheduler for automatic price updates every 5 minutes
- **werkzeug** — password hashing and security
- **python-dotenv** — secure API key management

## Project Structure

```
FinanceAdvisor/
├── app.py              # All Flask routes (793 lines)
├── models.py           # SQLAlchemy models (User, Asset, UserAsset, PriceHistory, Watchlist, ChatHistory, PortfolioAnalysis)
├── api_services.py     # Live price fetching (stocks, crypto, metals, web search)
├── crypto_prices.py    # CoinGecko API integration
├── stocks_prices.py    # yfinance integration
├── scheduler.py        # APScheduler — auto price updates every 5 minutes
├── tools.py            # OpenAI Function Calling tool definitions
├── requirements.txt
└── templates/
    ├── index.html      # Login / Register
    ├── dashboard.html  # Portfolio overview & chart
    ├── chat.html       # AI chat interface
    ├── analyse.html    # Portfolio analysis
    ├── watchlist.html  # Watchlist
    └── settings.html   # User profile settings
```

## API Overview

| Method | Route | Description |
|--------|-------|-------------|
| `POST` | `/register` | Register new user |
| `POST` | `/login` | Login |
| `GET` | `/users/<id>` | Get user profile |
| `PUT` | `/users/<id>/settings` | Update investment settings |
| `GET` | `/users/<id>/assets` | Get portfolio (live prices) |
| `POST` | `/users/<id>/assets` | Add asset to portfolio |
| `PUT` | `/users/<id>/assets/<id>/buy` | Record a buy (updates avg price) |
| `PUT` | `/users/<id>/assets/<id>/sell` | Record a sell |
| `GET` | `/users/<id>/portfolio/history` | Price history for chart |
| `POST` | `/portfolio/analyze` | AI portfolio analysis |
| `POST` | `/chat` | AI chat with Function Calling |
| `GET` | `/chat/history/<id>` | Get chat history |
| `GET/POST/DELETE` | `/users/<id>/watchlist` | Manage watchlist |
| `GET` | `/assets/search` | Search asset by name or symbol |

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
```
> Get your key at [platform.openai.com](https://platform.openai.com/api-keys)

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
- Integrating OpenAI Function Calling to let the AI fetch live data autonomously
- Using Pydantic Structured Output (`response_format`) for reliable JSON from LLMs
- Designing a relational SQLAlchemy database with 7 interconnected models
- Implementing secure user authentication with password hashing via `werkzeug`
- Running background tasks with APScheduler inside a Flask app context
- Fetching live financial data from multiple APIs (yfinance, CoinGecko)
- Combining user profile data with AI system prompts for personalized responses
- Separating concerns across multiple modules (routes, models, services, scheduler, tools)
