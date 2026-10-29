"""
portfolio/analysis.py - KI-gestützte Portfolio-Analyse mit Structured
Output und objektivem Diversifikationsscore (Herfindahl-Hirschman-Index).
"""

# Standard Library
import ast
import json

# Third Party
from flask import Blueprint, jsonify
from flask_login import current_user

# Lokale Imports
from fintrack.auth.session import current_user_key, protect_blueprint
from fintrack.extensions import db, get_openai_client, limiter
from fintrack.market.prices import get_current_price
from fintrack.models import Asset, PortfolioAnalysis, PortfolioAnalysisSchema, UserAsset

bp = Blueprint('analysis', __name__)
# Nur mit Anmeldung
protect_blueprint(bp)


def parse_stored_list(value):
    """
    Liest gespeicherte Empfehlungen als Liste. Neue Analysen sind als JSON
    gespeichert, ältere als Python-Text wie "['a', 'b']" - beide Formate
    werden unterstützt.
    """
    if not value:
        return []
    try:
        return json.loads(value)
    except ValueError:
        try:
            parsed = ast.literal_eval(value)
            return parsed if isinstance(parsed, list) else [str(parsed)]
        except (ValueError, SyntaxError):
            return [value]


def calculate_diversification_score(asset_values, total_value):
    """
    Berechnet einen Diversifikationsscore von 1-10 basierend auf dem
    Herfindahl-Hirschman-Index (HHI) - einem Standardmaß für
    Portfolio-Konzentration. Ein Portfolio mit einem einzigen Asset
    hat einen HHI von 1.0 (maximale Konzentration), ein Portfolio mit
    vielen gleichgewichteten Assets nähert sich 0 an. Der HHI wird
    hier auf eine 1-10-Skala umgerechnet, wobei 10 = maximal
    diversifiziert und 1 = maximal konzentriert bedeutet.
    """
    if total_value == 0 or not asset_values:
        return 1

    hhi = sum((value / total_value) ** 2 for value in asset_values)

    # HHI liegt zwischen 1/n (perfekt gleichverteilt) und 1 (ein Asset).
    # Wir invertieren und skalieren linear auf 1-10, wobei hhi=1 -> Score 1
    # und hhi nahe 0 -> Score nahe 10 ergibt.
    score = round(10 - (hhi * 9))
    return max(1, min(10, score))


@bp.route('/me/analyses', methods=['POST'])
@limiter.limit("10 per hour", key_func=current_user_key)
def analyze_portfolio():
    """
    KI-gestützte Portfolio-Analyse mit Pydantic Structured Output.
    Das LLM analysiert das Portfolio und gibt strukturierte Daten zurück.
    Der Gesamtwert wird nicht vom LLM übernommen, sondern im Backend
    berechnet und überschrieben, da LLMs bei der Aufsummierung von
    Zahlen unzuverlässig sind.
    Ergebnis wird in der DB gespeichert.
    """
    # Immer der angemeldete Nutzer - eine user_id im Body wird ignoriert
    user = current_user
    user_id = user.id

    # Alle Assets des Nutzers aus der DB holen
    user_assets = UserAsset.query.filter_by(user_id=user_id).filter(UserAsset.quantity > 0).all()

    # Nutzerdaten vorbereiten - falls Felder leer sind "not specified" setzen
    risk_profile = user.risk_profile if user.risk_profile else "not specified"
    investment_experience = user.investment_experience if user.investment_experience else "not specified"
    monthly_budget = user.monthly_budget if user.monthly_budget else "not specified"
    investment_horizon = user.investment_horizon if user.investment_horizon else "not specified"

    # Portfolio-Kontext aufbauen
    portfolio_context = ""
    total_value = 0
    asset_values = []  # Einzelwerte für die Diversifikations-Berechnung sammeln

    for user_asset in user_assets:
        asset = db.session.get(Asset, user_asset.asset_id)

        current_price = get_current_price(asset, unknown_type_default=user_asset.avg_buy_price)

        current_value = user_asset.quantity * current_price
        total_value += current_value
        asset_values.append(current_value)

        portfolio_context += (
            f"\n- {asset.name}: {user_asset.quantity} units"
            f"\n  Avg. buy price: {user_asset.avg_buy_price} {asset.currency}"
            f"\n  Current price: {current_price} {asset.currency}"
            f"\n  Current value: {current_value} {asset.currency}"
        )

    # System Prompt für Portfolio-Analyse
    # Pydantic übernimmt das JSON Format - kein "respond in JSON" nötig!
    messages = [
        {
            "role": "system",
            "content": (
                f"You are an experienced financial advisor. "
                f"Always respond in German. "
                f"Analyze the user's portfolio objectively. "
                f"Never give direct buy or sell recommendations. "
                f"\n\nUser profile:"
                f"\n- Risk profile: {risk_profile}"
                f"\n- Investment experience: {investment_experience}"
                f"\n- Monthly budget: {monthly_budget}"
                f"\n- Investment horizon: {investment_horizon}"
                f"\n\nUser portfolio:{portfolio_context}"
            )
        },
        {
            "role": "user",
            "content": "Please analyze my portfolio."  # Trigger für die Analyse
        }
    ]

    # Nachricht ans LLM schicken mit Pydantic Structured Output
    # response_format=PortfolioAnalysisSchema → LLM muss exakt dieses Format zurückgeben
    response = get_openai_client().beta.chat.completions.parse(
        model="gpt-4o-mini",
        messages=messages,
        temperature=0.3,
        response_format=PortfolioAnalysisSchema
    )

    # Pydantic Objekt aus der Antwort holen
    # .parsed → gibt direkt ein Python Objekt zurück, kein JSON parsen nötig!
    analysis = response.choices[0].message.parsed

    # Vom LLM berechneten Gesamtwert durch den exakten Backend-Wert ersetzen
    analysis.total_value = round(total_value, 2)

    # Diversifikationsscore objektiv über HHI berechnen - ist kein
    # Teil des Pydantic-Schemas, wird separat hinzugefügt
    diversification_score = calculate_diversification_score(asset_values, total_value)

    # Analyse in DB speichern
    new_analysis = PortfolioAnalysis(
        user_id=user_id,
        total_value=analysis.total_value,
        risk_assessment=analysis.risk_assessment,
        diversification_score=diversification_score,
        summary=analysis.summary,
        # Als echtes JSON speichern (früher Python-Text, an Apostrophen zerbrochen)
        recommendations=json.dumps(analysis.recommendations, ensure_ascii=False),
        allocation=json.dumps([item.model_dump() for item in analysis.allocation], ensure_ascii=False)
    )

    db.session.add(new_analysis)
    db.session.commit()

    # model_dump() enthält den Score nicht mehr (kein Pydantic-Feld) -
    # wird der Antwort manuell hinzugefügt
    result = analysis.model_dump()
    result['diversification_score'] = diversification_score

    return jsonify(result), 200


@bp.route('/me/analyses', methods=['GET'])
def get_portfolio_analyses():
    """Alle eigenen Portfolio-Analysen, neueste zuerst."""
    analyses = PortfolioAnalysis.query.filter_by(user_id=current_user.id)\
        .order_by(PortfolioAnalysis.created_at.desc()).all()

    result = []
    for analysis in analyses:
        result.append({
            "id": analysis.id,
            "total_value": analysis.total_value,
            "risk_assessment": analysis.risk_assessment,
            "diversification_score": analysis.diversification_score,
            "summary": analysis.summary,
            "recommendations": parse_stored_list(analysis.recommendations),
            "created_at": analysis.created_at.strftime('%d.%m.%Y %H:%M')
        })

    return jsonify(result), 200
