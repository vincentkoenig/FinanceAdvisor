"""
insight_logic.py - Generiert einen täglichen, proaktiven KI-Insight
pro Nutzer: fasst die Portfolio-Entwicklung der letzten 7 Tage und
den aktuellen Haushaltsbuch-Status in wenigen, natürlichen Sätzen
zusammen. Wird vom Scheduler täglich aufgerufen und in DailyInsight
gespeichert, damit die Home-Seite sie anzeigen kann.
"""

from datetime import datetime, timedelta

from openai import OpenAI

from models import db, User, UserAsset, Asset, PriceHistory, DailyInsight
from budget_logic import calculate_budget_summary


def calculate_portfolio_value_at(user_id, target_date):
    """
    Berechnet den ungefähren Portfolio-Gesamtwert eines Nutzers an
    einem bestimmten Datum, basierend auf den zu diesem Zeitpunkt
    gehaltenen Mengen (aktueller Stand, keine historische Mengen-
    Rekonstruktion) und den historischen Preisen aus PriceHistory.
    """
    holdings = UserAsset.query.filter_by(user_id=user_id).filter(UserAsset.quantity > 0).all()

    total = 0
    for holding in holdings:
        price_entry = PriceHistory.query.filter_by(asset_id=holding.asset_id) \
            .filter(PriceHistory.date <= target_date) \
            .filter(PriceHistory.price.isnot(None)) \
            .order_by(PriceHistory.date.desc()).first()

        if price_entry:
            total += holding.quantity * price_entry.price

    return total


def generate_insight_for_user(user_id, openai_client):
    """
    Generiert und speichert einen neuen DailyInsight für einen Nutzer.
    """
    user = db.session.get(User, user_id)
    if not user:
        return

    today = datetime.now()
    week_ago = today - timedelta(days=7)

    current_value = calculate_portfolio_value_at(user_id, today)
    week_ago_value = calculate_portfolio_value_at(user_id, week_ago)

    if week_ago_value > 0:
        change_percent = round(((current_value - week_ago_value) / week_ago_value) * 100, 1)
    else:
        change_percent = 0

    budget = calculate_budget_summary(user_id)

    prompt_context = (
        f"Portfolio-Wert heute: {round(current_value, 2)} EUR\n"
        f"Portfolio-Wert vor 7 Tagen: {round(week_ago_value, 2)} EUR\n"
        f"Veränderung: {change_percent}%\n"
        f"Einnahmen diesen Monat: {budget['current_month_income']} EUR\n"
        f"Fixkosten diesen Monat: {budget['current_month_fixed']} EUR\n"
        f"Variable Ausgaben diesen Monat: {budget['current_month_variable']} EUR\n"
        f"Saldo diesen Monat: {budget['current_month_balance']} EUR"
    )

    response = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a financial assistant that writes very short, natural "
                    "daily summaries in German for a personal finance app. "
                    "Write exactly 2-3 sentences, no headers, no bullet points, "
                    "no markdown formatting. Be specific with numbers. "
                    "Mention the most notable development first (portfolio change "
                    "or budget situation, whichever is more significant). "
                    "Keep a neutral, factual tone - never give buy/sell advice."
                )
            },
            {
                "role": "user",
                "content": f"Hier sind die aktuellen Zahlen:\n{prompt_context}"
            }
        ],
        temperature=0.4
    )

    insight_text = response.choices[0].message.content

    new_insight = DailyInsight(user_id=user_id, content=insight_text)
    db.session.add(new_insight)
    db.session.commit()


def generate_insights_for_all_users(openai_client):
    """Generiert einen neuen Insight für jeden Nutzer der App."""
    users = User.query.all()
    for user in users:
        generate_insight_for_user(user.id, openai_client)