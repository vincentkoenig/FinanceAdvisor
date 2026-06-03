"""
tools.py - OpenAI Function Calling Tool Definitionen
Definiert die Tools die das LLM benutzen kann um aktuelle Marktdaten abzurufen.
Das LLM entscheidet selbst wann es welches Tool aufrufen soll.
"""

tools = [
    {
        "type": "function",     # Sagt OpenAI: "Das hier ist eine Funktion die aufgerufen werden kann"
        "function": {
            "name": "get_crypto_price",     # Der Name der Funktion – muss exakt gleich sein wie in api_services.py
            "description": "Get the current price of a cryptocurrency in EUR",      # Erklärt dem LLM wann es diese Funktion benutzen soll.
            "parameters": {
                "type": "object",   # Sagt: "Die Funktion bekommt Parameter als Objekt übergeben" – also als Dictionary
                "properties": {     # Definiert welche Parameter die Funktion hat
                    "coin_id": {
                        "type": "string",   # coin_id muss ein Text sein
                        "description": "Cryptocurrency ID e.g. bitcoin, ethereum, solana"   # erklärt dem LLM was es dort reinschreiben soll
                    }
                },
                "required": ["coin_id"]     # Sagt: "coin_id ist Pflicht" – das LLM muss immer einen Wert mitschicken
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