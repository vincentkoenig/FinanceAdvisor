"""
chat/routes.py - Chat mit dem KI-Finanzberater inkl. Function Calling
(Live-Preise, Websuche, Haushaltsbuch) und gespeichertem Verlauf.
"""

# Standard Library
import json
from datetime import datetime

# Third Party
from flask import Blueprint, jsonify
from pydantic import Field
from flask_login import current_user

# Lokale Imports
from fintrack.api import RequestModel, parse_body
from fintrack.auth.session import current_user_key, protect_blueprint
from fintrack.budget.service import calculate_budget_summary
from fintrack.chat.tools import tools
from fintrack.extensions import db, get_openai_client, limiter
from fintrack.market.data import get_crypto_price, search_web
from fintrack.market.service import quote_in_eur
from fintrack.market.yahoo import yahoo_symbol
from fintrack.models import ChatHistory

bp = Blueprint('chat', __name__)
# Nur mit Anmeldung
protect_blueprint(bp)

# Wie viele Chat-Nachrichten maximal als Kontext ans LLM geschickt werden (Sliding Window)
MAX_CHAT_HISTORY = 20


class ChatMessage(RequestModel):
    message: str = Field(min_length=1, max_length=4000)


@bp.route('/me/chat', methods=['POST'])
@limiter.limit("20 per minute; 300 per day", key_func=current_user_key)
def chat():
    """
    Chat mit dem KI-Finanzberater.
    Nutzt Function Calling damit das LLM Live-Preise abrufen kann.
    Chatverlauf wird in der DB gespeichert für Kontext bei nächster Nachricht.
    """
    message = parse_body(ChatMessage).message

    # Immer der angemeldete Nutzer - eine user_id im Body wird ignoriert
    user = current_user
    user_id = user.id

    # Bisherigen Chatverlauf aus DB holen
    # Wird ans LLM geschickt damit es den Kontext versteht
    chat_history = ChatHistory.query.filter_by(user_id=user_id) \
        .order_by(ChatHistory.id.desc()) \
        .limit(MAX_CHAT_HISTORY) \
        .all()

    # LLM braucht Nachrichten chronologisch zuerst
    chat_history.reverse()

    # Nutzerdaten vorbereiten - falls Felder leer sind "not specified" setzen
    risk_profile = user.risk_profile if user.risk_profile else "not specified"
    investment_experience = user.investment_experience if user.investment_experience else "not specified"
    monthly_budget = user.monthly_budget if user.monthly_budget else "not specified"
    investment_horizon = user.investment_horizon if user.investment_horizon else "not specified"

    current_year = datetime.now().year

    # System Prompt als erstes Element der messages Liste
    # Definiert die Rolle und das Verhalten des LLM
    messages = [
        {
            "role": "system",
            "content": (
                f"You are an experienced financial advisor. "
                f"Always respond in German. "
                f"Never give direct buy or sell recommendations. "
                f"STRICT RULE: If the question asks for a price or current value, answer in ONE sentence only. "
                f"For all other questions: adapt your format to the question type. "
                f"- Comparison questions: use a table "
                f"- Explanation questions: use concrete examples with real numbers "
                f"- Strategy questions: explain pros and cons naturally in text "
                f"Always use concrete numbers and real examples. "
                f"Never use a rigid format - every answer should feel natural and tailored to the question. "
                f"Refer to the user's profile when relevant. "
                f"Never use numbered lists. "
                f"Do not always end with a follow-up question or example - only when it adds real value. "
                f"NEVER end your response with '💡 Beispiel' or '❓ Interessiert Sie auch'. "
                f"Only add examples or follow-up questions when they are naturally part of the explanation. "
                f"NEVER use numbered lists (1. 2. 3.). Use natural paragraphs or bullet points with '-' instead. "
                f"When using the search_web tool for news or current events, always include "
                f"the current year ({current_year}) or a recency term like 'aktuell' / 'latest' "
                f"in your search query, to avoid retrieving outdated results. "
                f"\n\nUser profile:"
                f"\n- Risk profile: {risk_profile}"
                f"\n- Investment experience: {investment_experience}"
                f"\n- Monthly budget: {monthly_budget}"
                f"\n- Investment horizon: {investment_horizon}"
            )
        }
    ]

    # Bisherigen Chatverlauf in OpenAI Format umwandeln und hinzufügen
    # So versteht das LLM den Kontext des Gesprächs
    for entry in chat_history:
        messages.append({
            "role": entry.role,       # 'user' oder 'assistant'
            "content": entry.message  # Text der Nachricht
        })

    # Neue Nachricht des Nutzers hinzufügen
    messages.append({
        "role": "user",
        "content": message
    })

    # Komplette messages Liste ans LLM schicken
    # temperature=0.3 → professionell aber nicht zu roboterhaft
    response = get_openai_client().chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        temperature=0.3,
        tools=tools
    )

    # Prüfen ob das LLM ein oder mehrere Tools aufrufen will
    if response.choices[0].message.tool_calls:
        # Assistant-Nachricht mit allen Tool-Calls zur History hinzufügen -
        # muss vor den einzelnen Tool-Antworten stehen
        messages.append(response.choices[0].message)

        # Für JEDEN angeforderten Tool-Call eine passende Antwort erzeugen -
        # OpenAI verlangt zwingend eine Antwort pro tool_call_id, sonst
        # schlägt der nächste API-Call mit einem BadRequestError fehl
        for tool_call in response.choices[0].message.tool_calls:
            function_name = tool_call.function.name
            function_args = json.loads(tool_call.function.arguments)

            # Richtige Funktion aufrufen basierend auf function_name
            if function_name == "get_crypto_price":
                result = get_crypto_price(function_args['coin_id'])
            elif function_name == "get_stock_price":
                result = quote_in_eur(function_args['symbol'])
            elif function_name == "get_metal_price":
                result = quote_in_eur(yahoo_symbol(function_args['symbol'].upper()))
            elif function_name == "search_web":
                result = search_web(function_args['query'])
            elif function_name == "get_budget_status":
                result = calculate_budget_summary(user_id)
            else:
                result = None

            # Ergebnis dieses einzelnen Tool-Calls zurück ans LLM schicken
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": str(result)
            })

        # Zweiter API Call - LLM formuliert finale Antwort mit allen Tool-Ergebnissen
        second_response = get_openai_client().chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            temperature=0.3
        )
        llm_reply = second_response.choices[0].message.content

    else:
        # Kein Tool Call - normale Textantwort
        llm_reply = response.choices[0].message.content

    # Nutzer-Nachricht in DB speichern
    new_user_message = ChatHistory(user_id=user_id, message=message, role="user")
    db.session.add(new_user_message)

    # LLM-Antwort in DB speichern
    # Wird beim nächsten Chat als Kontext verwendet
    new_llm_reply = ChatHistory(user_id=user_id, message=llm_reply, role="assistant")
    db.session.add(new_llm_reply)

    db.session.commit()

    return jsonify({"reply": llm_reply}), 200


@bp.route('/me/chat/history', methods=['GET'])
def get_chat_history():
    """Chatverlauf eines Nutzers abrufen"""
    chat_history = ChatHistory.query.filter_by(user_id=current_user.id).order_by(ChatHistory.id).all()

    result = []
    for entry in chat_history:
        result.append({
            "role": entry.role,
            "message": entry.message
        })

    return jsonify(result), 200
