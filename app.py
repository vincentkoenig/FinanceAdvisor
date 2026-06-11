# ─── IMPORTS ──────────────────────────────────────────────────────────────────

# Standard Library
import json
import os       # Operating System: Gibt Zugriff auf Funktionen des Betriebssystems
import re       # Regular Expressions (kurz: Regex) sind Muster um Text zu durchsuchen und zu validieren
from datetime import datetime

# Third Party
import yfinance as yf
from dotenv import load_dotenv
from flask import Flask, request, jsonify, render_template
from openai import OpenAI
from werkzeug.security import generate_password_hash, check_password_hash

# Lokale Imports
from api_services import get_crypto_price, get_stock_price, get_metal_price, get_historical_prices, search_web
from models import (db, User, Asset, UserAsset, PriceHistory,
                    Watchlist, ChatHistory, PortfolioAnalysis, PortfolioAnalysisSchema)
from scheduler import start_scheduler
from tools import tools


# ─── KONFIGURATION ────────────────────────────────────────────────────────────

# .env Datei laden - muss vor os.getenv() stehen!
load_dotenv()

# Verbindung zu OpenAI herstellen - API Key sicher aus .env holen
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Flask App erstellen
app = Flask(__name__)

# Datenbank konfigurieren - Pfad zur SQLite Datei
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///finance_advisor.db'

# SQLAlchemy mit der Flask App verbinden
db.init_app(app)

# Tabellen erstellen wenn sie noch nicht existieren
# app_context() sagt Flask welche App gerade aktiv ist
with app.app_context():
    db.create_all()


# ─── SEITEN ROUTEN ────────────────────────────────────────────────────────────

@app.route('/')
def home():
    """Startseite - Login/Register Seite"""
    return render_template('index.html')


@app.route('/dashboard')
def dashboard_page():
    """Dashboard Seite - Portfolio Übersicht"""
    return render_template('dashboard.html')


@app.route('/chat-page')
def chat_page():
    """Chat Seite - KI Finanzberater"""
    return render_template('chat.html')


@app.route('/analyse-page')
def analyse_page():
    """Analyse Seite - Portfolio Analyse"""
    return render_template('analyse.html')


@app.route('/watchlist-page')
def watchlist_page():
    """Watchlist Seite - Assets beobachten"""
    return render_template('watchlist.html')


@app.route('/settings-page')
def settings_page():
    """Einstellungen Seite - Nutzerprofil"""
    return render_template('settings.html')


# ─── AUTH ENDPOINTS ───────────────────────────────────────────────────────────

@app.route('/register', methods=['POST'])
def register():
    """
    Neuen Nutzer registrieren.
    Email wird validiert und Username automatisch aus Email abgeleitet.
    Passwort wird gehasht gespeichert.
    """
    data = request.json
    email = data['email']
    password = data['password']

    # Email Validierung mit Regex
    if not re.match(r'^[^@]+@[^@]+\.[^@]+$', email):
        return jsonify({"error": "Bitte eine gültige Email eingeben"}), 400

    # Username automatisch aus Email ableiten z.B. vincent@test.com → vincent
    username = email.split('@')[0]

    # Passwort hashen - niemals als reinen Text speichern!
    hashed_password = generate_password_hash(password)

    # Neuen Nutzer erstellen und in der Datenbank speichern
    new_user = User(username=username, email=email, password=hashed_password)
    db.session.add(new_user)
    db.session.commit()

    # 201 = Created - Nutzer wurde erfolgreich erstellt
    return jsonify({"message": "User registered successfully", "user_id": new_user.id}), 201


@app.route('/login', methods=['POST'])
def login():
    """
    Nutzer einloggen.
    Email und Passwort werden überprüft.
    Gibt user_id zurück damit Frontend sie im localStorage speichern kann.
    """
    data = request.json
    email = data['email']
    password = data['password']

    # Nutzer in der Datenbank anhand der Email suchen
    # .first() gibt den ersten Treffer zurück oder None
    user = User.query.filter_by(email=email).first()

    # Wenn Nutzer nicht gefunden → 404 Not Found
    if not user:
        return jsonify({"error": "User not found"}), 404

    # Passwort überprüfen - vergleicht eingegebenes Passwort mit gespeichertem Hash
    # Passwort wird nie entschlüsselt - nur die Hashes werden verglichen!
    if not check_password_hash(user.password, password):
        return jsonify({"error": "Wrong password"}), 401  # 401 = Unauthorized

    # Wenn alles stimmt → 200 OK
    return jsonify({"message": "Login successful", "user_id": user.id}), 200


# ─── USER ENDPOINTS ───────────────────────────────────────────────────────────

@app.route('/users/<user_id>', methods=['GET'])
def get_user(user_id):
    """Nutzerprofil abrufen - Passwort wird nie zurückgegeben!"""
    user = db.session.get(User, user_id)

    if not user:
        return jsonify({"error": "User not found"}), 404

    return jsonify({
        "id": user.id,
        "username": user.username,
        "email": user.email
    }), 200


@app.route('/users/<user_id>/settings', methods=['PUT'])
def settings(user_id):
    """
    Nutzereinstellungen aktualisieren.
    Risikoprofil, Erfahrung, Budget und Horizont werden gespeichert.
    Diese Daten werden vom LLM für personalisierte Antworten verwendet.
    """
    data = request.json
    risk_profile = data['risk_profile']
    investment_experience = data['investment_experience']
    monthly_budget = data['monthly_budget']
    investment_horizon = data['investment_horizon']

    user = db.session.get(User, user_id)

    if not user:
        return jsonify({"error": "User not found"}), 404

    # Bestehende Felder aktualisieren
    # Kein db.session.add() nötig - SQLAlchemy erkennt automatisch Änderungen!
    user.risk_profile = risk_profile
    user.investment_experience = investment_experience
    user.monthly_budget = monthly_budget
    user.investment_horizon = investment_horizon

    db.session.commit()

    return jsonify({"message": "Settings successfully updated"}), 200


# ─── ASSET ENDPOINTS ──────────────────────────────────────────────────────────

@app.route('/assets/<asset_id>', methods=['GET'])
def get_asset(asset_id):
    """
    Asset Details abrufen inkl. aktuellem Preis.
    Preis wird live von yfinance oder CoinGecko geholt.
    """
    asset = db.session.get(Asset, asset_id)

    if not asset:
        return jsonify({"error": "Asset not found"}), 404

    # Aktuellen Preis je nach Asset-Typ holen
    if asset.asset_type in ("stock", "etf"):
        current_price = get_stock_price(asset.symbol)
    elif asset.asset_type == "crypto":
        current_price = get_crypto_price(asset.symbol)
    elif asset.asset_type == "metal":
        current_price = get_metal_price(asset.symbol)
    else:
        current_price = None

    return jsonify({
        "id": asset.id,
        "name": asset.name,
        "symbol": asset.symbol,
        "asset_type": asset.asset_type,
        "current_price": current_price
    }), 200


@app.route('/assets/search', methods=['GET'])
def search_asset():
    """
    Asset suchen - zuerst in DB, dann mit yfinance.
    Nutzer kann Name oder Symbol eingeben z.B. 'Tesla' oder 'TSLA'.
    Wenn Asset nicht in DB ist wird es automatisch erstellt.
    """
    query = request.args.get('query')

    # Erst in DB nach Symbol suchen
    asset = Asset.query.filter_by(symbol=query.upper()).first()

    # Wenn nicht gefunden → mit yfinance suchen und erstellen
    if not asset:
        try:
            # Mit yfinance nach Name oder Symbol suchen
            search = yf.Search(query)
            quotes = search.quotes

            if not quotes:
                return jsonify({"error": f"Asset '{query}' nicht gefunden!"}), 404

            # Erstes Ergebnis nehmen
            first_result = quotes[0]
            symbol = first_result['symbol']
            name = first_result.get('longname', first_result.get('shortname', symbol))

            # Preis validieren um sicherzustellen dass das Asset handelbar ist
            ticker = yf.Ticker(symbol)
            price = ticker.fast_info['lastPrice']

            # Asset in DB erstellen
            asset = Asset(
                name=name,
                symbol=symbol,
                asset_type='stock',
                currency='EUR'
            )
            db.session.add(asset)
            db.session.commit()

            # Historische Preise automatisch laden und speichern
            historical_prices = get_historical_prices(symbol)

            if historical_prices:
                for price_data in historical_prices:
                    new_price = PriceHistory(
                        asset_id=asset.id,
                        date=datetime.strptime(price_data['date'], '%Y-%m-%d'),
                        price=price_data['price'],
                        currency='EUR'
                    )
                    db.session.add(new_price)
                db.session.commit()
                print(f"Historische Preise für {symbol} gespeichert!")

        except Exception as e:
            print(f"Error searching asset: {e}")
            return jsonify({"error": f"Asset '{query}' nicht gefunden!"}), 404

    return jsonify({
        "id": asset.id,
        "name": asset.name,
        "symbol": asset.symbol,
        "asset_type": asset.asset_type
    }), 200


@app.route('/assets/<asset_id>/prices', methods=['POST'])
def add_prices(asset_id):
    """Neuen Preis für ein Asset hinzufügen"""
    data = request.json
    # Datum von String in Python datetime Objekt umwandeln
    date = datetime.strptime(data['date'], '%Y-%m-%d')
    price = data['price']
    currency = data['currency']

    new_price = PriceHistory(asset_id=asset_id, date=date, price=price, currency=currency)
    db.session.add(new_price)
    db.session.commit()

    return jsonify({"message": "Price successfully added"}), 201


# ─── USER ASSET ENDPOINTS ─────────────────────────────────────────────────────

@app.route('/users/<user_id>/assets', methods=['GET'])
def get_user_assets(user_id):
    """
    Alle Assets des Nutzers abrufen.
    Nur Assets mit quantity > 0 werden zurückgegeben.
    Aktueller Preis wird live von yfinance oder CoinGecko geholt.
    """
    # Nur Assets mit quantity > 0 holen - verkaufte Assets ausblenden
    user_assets = UserAsset.query.filter_by(user_id=user_id).filter(UserAsset.quantity > 0).all()

    result = []

    for user_asset in user_assets:
        # Asset aus DB holen um Name und Symbol zu bekommen
        asset = db.session.get(Asset, user_asset.asset_id)

        # Aktuellen Preis je nach Asset-Typ holen
        if asset.asset_type in ("stock", "etf"):
            current_price = get_stock_price(asset.symbol)
        elif asset.asset_type == "crypto":
            current_price = get_crypto_price(asset.symbol)
        elif asset.asset_type == "metal":
            current_price = get_metal_price(asset.symbol)
        else:
            current_price = user_asset.avg_buy_price

        result.append({
            "asset_id": user_asset.asset_id,
            "name": asset.name,
            "symbol": asset.symbol,
            "quantity": user_asset.quantity,
            "avg_buy_price": user_asset.avg_buy_price,
            "bought_at": user_asset.bought_at,
            "status": user_asset.status,
            "current_price": current_price
        })

    return jsonify(result), 200


@app.route('/users/<user_id>/assets', methods=['POST'])
def add_user_asset(user_id):
    """Neues Asset dem Nutzer zuweisen"""
    data = request.json
    asset_id = data['asset_id']
    quantity = data['quantity']
    avg_buy_price = data['avg_buy_price']
    # Datum von String in Python datetime Objekt umwandeln
    bought_at = datetime.strptime(data['bought_at'], '%Y-%m-%d')
    status = data['status']

    user_asset = UserAsset(
        user_id=user_id,
        asset_id=asset_id,
        quantity=quantity,
        avg_buy_price=avg_buy_price,
        bought_at=bought_at,
        status=status
    )
    db.session.add(user_asset)
    db.session.commit()

    return jsonify({"message": "User asset successfully added"}), 201


@app.route('/users/<user_id>/assets/<asset_id>/buy', methods=['PUT'])
def add_buy(user_id, asset_id):
    """
    Weiteren Kauf eines Assets hinzufügen.
    Berechnet neuen Durchschnittspreis basierend auf altem und neuem Kauf.
    """
    data = request.json
    quantity = data['quantity']
    price = data['price']

    user_asset = UserAsset.query.filter_by(user_id=user_id, asset_id=asset_id).first()

    if not user_asset:
        return jsonify({"error": "Asset not found"}), 404

    # Neuen Durchschnittspreis berechnen
    # (alter Wert + neuer Wert) / neue Gesamtmenge
    old_value = user_asset.quantity * user_asset.avg_buy_price
    new_value = float(quantity) * float(price)
    new_quantity = user_asset.quantity + float(quantity)
    new_avg_price = (old_value + new_value) / new_quantity

    # Werte aktualisieren
    user_asset.quantity = new_quantity
    user_asset.avg_buy_price = round(new_avg_price, 2)

    db.session.commit()

    return jsonify({"message": "Buy successfully added"}), 200


@app.route('/users/<user_id>/assets/<asset_id>/sell', methods=['PUT'])
def add_sell(user_id, asset_id):
    """
    Verkauf eines Assets hinzufügen.
    Reduziert die Menge - wenn alles verkauft wird Status auf 'sold' gesetzt.
    """
    data = request.json
    quantity = data['quantity']

    user_asset = UserAsset.query.filter_by(user_id=user_id, asset_id=asset_id).first()

    if not user_asset:
        return jsonify({"error": "Asset not found"}), 404

    # Prüfen ob genug Anteile vorhanden sind
    if float(quantity) > user_asset.quantity:
        return jsonify({"error": "Nicht genug Anteile!"}), 400

    # Menge reduzieren
    user_asset.quantity -= float(quantity)

    # Wenn alles verkauft → Status auf sold setzen
    if user_asset.quantity == 0:
        user_asset.status = "sold"

    db.session.commit()

    return jsonify({"message": "Sell successfully added"}), 200


# ─── PORTFOLIO ENDPOINTS ──────────────────────────────────────────────────────

@app.route('/users/<user_id>/portfolio/history', methods=['GET'])
def get_portfolio_history(user_id):
    """
    Preishistorie aller aktiven Assets des Nutzers abrufen.
    Wird für den Liniendiagramm auf dem Dashboard verwendet.
    Nur Assets mit quantity > 0 werden berücksichtigt.
    """
    # Nur aktive Assets holen - verkaufte Assets ausblenden
    user_assets = UserAsset.query.filter_by(user_id=user_id).filter(UserAsset.quantity > 0).all()

    result = {}

    for user_asset in user_assets:
        asset = db.session.get(Asset, user_asset.asset_id)

        # Preishistorie für dieses Asset holen - älteste zuerst
        prices = PriceHistory.query.filter_by(asset_id=user_asset.asset_id) \
            .order_by(PriceHistory.date.asc()).all()

        # Preis × Menge = Portfoliowert für dieses Asset
        result[asset.name] = [
            {
                "date": price.date.strftime('%Y-%m-%d'),
                "price": price.price * user_asset.quantity
            }
            for price in prices
        ]

    return jsonify(result), 200


@app.route('/portfolio/analyze', methods=['POST'])
def analyze_portfolio():
    """
    KI-gestützte Portfolio-Analyse mit Pydantic Structured Output.
    Das LLM analysiert das Portfolio und gibt strukturierte Daten zurück.
    Ergebnis wird in der DB gespeichert.
    """
    data = request.json
    user_id = data['user_id']

    user = db.session.get(User, user_id)

    if not user:
        return jsonify({"error": "User not found"}), 404

    # Alle Assets des Nutzers aus der DB holen
    user_assets = UserAsset.query.filter_by(user_id=user_id).all()

    # Nutzerdaten vorbereiten - falls Felder leer sind "not specified" setzen
    risk_profile = user.risk_profile if user.risk_profile else "not specified"
    investment_experience = user.investment_experience if user.investment_experience else "not specified"
    monthly_budget = user.monthly_budget if user.monthly_budget else "not specified"
    investment_horizon = user.investment_horizon if user.investment_horizon else "not specified"

    # Portfolio-Kontext aufbauen
    # Das LLM bekommt alle Assets mit Menge, Kaufpreis und aktuellem Preis
    portfolio_context = ""
    for user_asset in user_assets:
        asset = db.session.get(Asset, user_asset.asset_id)

        # Aktuellen Preis je nach Asset-Typ holen
        if asset.asset_type in ("stock", "etf"):
            current_price = get_stock_price(asset.symbol)
        elif asset.asset_type == "crypto":
            current_price = get_crypto_price(asset.symbol)
        elif asset.asset_type == "metal":
            current_price = get_metal_price(asset.symbol)
        else:
            current_price = user_asset.avg_buy_price

        current_value = user_asset.quantity * current_price

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
    response = client.beta.chat.completions.parse(
        model="gpt-4o-mini",
        messages=messages,
        temperature=0.3,
        response_format=PortfolioAnalysisSchema
    )

    # Pydantic Objekt aus der Antwort holen
    # .parsed → gibt direkt ein Python Objekt zurück, kein JSON parsen nötig!
    analysis = response.choices[0].message.parsed

    # Analyse in DB speichern
    new_analysis = PortfolioAnalysis(
        user_id=user_id,
        total_value=analysis.total_value,
        risk_assessment=analysis.risk_assessment,
        diversification_score=analysis.diversification_score,
        summary=analysis.summary,
        recommendations=str(analysis.recommendations),  # Liste als Text speichern
        allocation=str(analysis.allocation)              # Pydantic Objekte als Text speichern
    )

    db.session.add(new_analysis)
    db.session.commit()

    # model_dump() wandelt Pydantic Objekt in Dictionary um das jsonify verarbeiten kann
    return jsonify(analysis.model_dump()), 200


@app.route('/users/<user_id>/portfolio/analyses', methods=['GET'])
def get_portfolio_analyses(user_id):
    """Alle Portfolio-Analysen eines Nutzers abrufen"""
    analyses = PortfolioAnalysis.query.filter_by(user_id=user_id)\
        .order_by(PortfolioAnalysis.created_at.desc()).all()

    result = []
    for analysis in analyses:
        result.append({
            "id": analysis.id,
            "total_value": analysis.total_value,
            "risk_assessment": analysis.risk_assessment,
            "diversification_score": analysis.diversification_score,
            "summary": analysis.summary,
            "recommendations": analysis.recommendations,
            "created_at": analysis.created_at.strftime('%d.%m.%Y %H:%M')
        })

    return jsonify(result), 200


# ─── WATCHLIST ENDPOINTS ──────────────────────────────────────────────────────

@app.route('/users/<user_id>/watchlist', methods=['POST'])
def add_to_watchlist(user_id):
    """Asset zur Watchlist hinzufügen"""
    data = request.json
    asset_id = data['asset_id']

    # added_at wird automatisch auf aktuelle Zeit gesetzt
    new_watchlist = Watchlist(user_id=user_id, asset_id=asset_id)
    db.session.add(new_watchlist)
    db.session.commit()

    return jsonify({"message": "Watchlist successfully updated"}), 201


@app.route('/users/<user_id>/watchlist', methods=['GET'])
def get_watchlist(user_id):
    """Alle Assets der Watchlist eines Nutzers abrufen"""
    assets = Watchlist.query.filter_by(user_id=user_id).all()

    result = []
    for asset in assets:
        result.append({
            "user_id": asset.user_id,
            "asset_id": asset.asset_id
        })

    return jsonify(result), 200


@app.route('/users/<user_id>/watchlist/<asset_id>', methods=['DELETE'])
def delete_asset_from_watchlist(user_id, asset_id):
    """Asset aus der Watchlist entfernen"""
    watchlist_item = Watchlist.query.filter_by(user_id=user_id, asset_id=asset_id).first()

    if not watchlist_item:
        return jsonify({"error": "Item not found"}), 404

    db.session.delete(watchlist_item)
    db.session.commit()

    return jsonify({"message": "Watchlist successfully updated"}), 200


# ─── CHAT ENDPOINTS ───────────────────────────────────────────────────────────

@app.route('/chat', methods=['POST'])
def chat():
    """
    Chat mit dem KI-Finanzberater.
    Nutzt Function Calling damit das LLM Live-Preise abrufen kann.
    Chatverlauf wird in der DB gespeichert für Kontext bei nächster Nachricht.
    """
    data = request.json
    user_id = data['user_id']
    message = data['message']

    # Nutzer aus DB holen um Profildaten zu erhalten
    user = db.session.get(User, user_id)

    # Bisherigen Chatverlauf aus DB holen
    # Wird ans LLM geschickt damit es den Kontext versteht
    chat_history = ChatHistory.query.filter_by(user_id=user_id).all()

    # Nutzerdaten vorbereiten - falls Felder leer sind "not specified" setzen
    risk_profile = user.risk_profile if user.risk_profile else "not specified"
    investment_experience = user.investment_experience if user.investment_experience else "not specified"
    monthly_budget = user.monthly_budget if user.monthly_budget else "not specified"
    investment_horizon = user.investment_horizon if user.investment_horizon else "not specified"

    # System Prompt als erstes Element der messages Liste
    # Definiert die Rolle und das Verhalten des LLM
    messages = [
        {
            "role": "system",
            "content": (
                f"You are an experienced financial advisor. "
                f"Always respond in German. "
                f"Never give direct buy or sell recommendations. "
                f"STRICT RULE: If the question asks for a price or current value, answer in ONE sentence only. Example: 'Der aktuelle Bitcoin-Kurs liegt bei 53.000 USD.' Nothing more. "
                f"For all other questions use this structure: short explanation, ✅ Vorteile, ⚠️ Nachteile, 💡 Beispiel, ❓ Interessiert Sie auch. "
                f"Never use numbered lists. "
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
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        temperature=0.3,
        tools=tools
    )

    # Prüfen ob das LLM ein Tool aufrufen will
    if response.choices[0].message.tool_calls:
        tool_call = response.choices[0].message.tool_calls[0]
        function_name = tool_call.function.name
        function_args = json.loads(tool_call.function.arguments)

        # Richtige Funktion aufrufen basierend auf function_name
        if function_name == "get_crypto_price":
            result = get_crypto_price(function_args['coin_id'])
        elif function_name == "get_stock_price":
            result = get_stock_price(function_args['symbol'])
        elif function_name == "get_metal_price":
            result = get_metal_price(function_args['symbol'])
        elif function_name == "search_web":
            result = search_web(function_args['query'])

        # Ergebnis zurück ans LLM schicken für finale Antwort
        messages.append(response.choices[0].message)
        messages.append({
            "role": "tool",
            "tool_call_id": tool_call.id,
            "content": str(result)
        })

        # Zweiter API Call - LLM formuliert finale Antwort mit Tool-Ergebnis
        second_response = client.chat.completions.create(
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


@app.route('/chat/history/<user_id>', methods=['GET'])
def get_chat_history(user_id):
    """Chatverlauf eines Nutzers abrufen"""
    chat_history = ChatHistory.query.filter_by(user_id=user_id).all()

    result = []
    for entry in chat_history:
        result.append({
            "role": entry.role,
            "message": entry.message
        })

    return jsonify(result), 200


# ─── PREIS ENDPOINTS ──────────────────────────────────────────────────────────

@app.route('/update-prices', methods=['POST'])
def manual_update_prices():
    """
    Manuelle Preisaktualisierung - nützlich wenn Scheduler nicht gelaufen ist.
    Ruft update_prices() aus scheduler.py auf.
    """
    from scheduler import update_prices
    update_prices(app)
    return jsonify({"message": "Prices updated successfully"}), 200


# ─── START ────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    # Scheduler starten - aktualisiert Preise automatisch alle 5 Minuten
    start_scheduler(app)
    # debug=True → automatischer Neustart bei Änderungen
    app.run(debug=True)