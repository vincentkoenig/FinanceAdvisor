"""
tools.py - OpenAI Function Calling Tool Definitionen
Definiert die Tools die das LLM benutzen kann um aktuelle Marktdaten abzurufen.
Das LLM entscheidet selbst wann es welches Tool aufrufen soll.
"""

tools = [
    {
        "type": "function",
        "function": {
            "name": "get_crypto_price",
            "description": "Get the current price of a cryptocurrency in EUR",
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
            "description": "Get the current price of a stock or ETF in USD",
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
            "description": "Get the current price of a precious metal in USD",
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
    }
]