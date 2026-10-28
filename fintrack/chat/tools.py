"""
tools.py - OpenAI Function Calling Tool Definitionen
Definiert die Tools die das LLM benutzen kann:
- get_crypto_price   → aktuellen Krypto-Preis abrufen
- get_stock_price    → aktuellen Aktien-Preis abrufen
- get_metal_price    → aktuellen Edelmetall-Preis abrufen
- search_web         → aktuelle Informationen aus dem Web suchen
- get_budget_status  → Haushaltsbuch-Status des Nutzers abrufen
Das LLM entscheidet selbst wann es welches Tool aufrufen soll.
"""

tools = [
    {
        "type": "function",
        "function": {
            "name": "get_crypto_price",
            "description": (
                "Get the current price of a cryptocurrency in EUR. "
                "Use this when the user asks about the current price of a cryptocurrency."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "coin_id": {
                        "type": "string",
                        "description": "Cryptocurrency ID e.g. bitcoin, ethereum, solana"
                    }
                },
                "required": ["coin_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_stock_price",
            "description": (
                "Get the current price of a stock or ETF in EUR. "
                "Use this when the user asks about the current price of a stock or ETF."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "Stock symbol e.g. AAPL, MSFT, NVDA"
                    }
                },
                "required": ["symbol"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_metal_price",
            "description": (
                "Get the current price of a precious metal in EUR. "
                "Use this when the user asks about the current price of gold or silver."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "Metal symbol - GOLD or SILVER"
                    }
                },
                "required": ["symbol"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_web",
            "description": (
                "ALWAYS use this tool when the user asks about: "
                "current news, recent events, why something is happening NOW, "
                "current market conditions, or any question about recent developments. "
                "Search the web for current financial news and information."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query e.g. 'Bitcoin price drop reason 2026'"
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_budget_status",
            "description": (
                "Get the user's household budget status - current month's income, "
                "fixed costs, variable expenses, balance, and the cumulative cash "
                "balance since tracking began. Use this when the user asks about "
                "their budget, savings, monthly expenses, income, or whether they "
                "can afford something based on their current financial situation."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    }
]