"""
pages.py - Routen, die HTML-Seiten ausliefern. Die Daten holen sich die
Seiten anschließend per JavaScript über die API-Routen der anderen Bereiche.
"""

from flask import Blueprint, render_template

bp = Blueprint('pages', __name__)


@bp.route('/')
def home():
    """Startseite - Login/Register Seite"""
    return render_template('index.html')


@bp.route('/home-page')
def home_page():
    """Home Seite - Gesamtübersicht über Vermögen (Portfolio + Cash)"""
    return render_template('home.html')


@bp.route('/portfolio-page')
def portfolio_page():
    """Portfolio Seite - Aktien, Krypto, Edelmetalle Übersicht"""
    return render_template('portfolio.html')


@bp.route('/budget-page')
def budget_page():
    """Haushaltsbuch Seite - Einnahmen und Ausgaben tracken"""
    return render_template('budget.html')


@bp.route('/chat-page')
def chat_page():
    """Chat Seite - KI Finanzberater"""
    return render_template('chat.html')


@bp.route('/analyse-page')
def analyse_page():
    """Analyse Seite - Portfolio Analyse"""
    return render_template('analyse.html')


@bp.route('/settings-page')
def settings_page():
    """Einstellungen Seite - Nutzerprofil"""
    return render_template('settings.html')
