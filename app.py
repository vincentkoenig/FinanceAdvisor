from flask import Flask, request, jsonify, render_template
from werkzeug.security import generate_password_hash, check_password_hash  # für sicheres Passwort-Hashing
from models import db, User, Asset, UserAsset, PriceHistory, Watchlist, ChatHistory, PortfolioAnalysis, PortfolioAnalysisSchema
from datetime import datetime
from dotenv import load_dotenv
import os
from openai import OpenAI
import json
from api_services import get_crypto_price, get_stock_price, get_metal_price
from tools import tools
from scheduler import start_scheduler
import re

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

@app.route('/')
def home():
    # Startseite - zeigt dass die API läuft
    return render_template('index.html')


@app.route('/register', methods=['POST'])
def register():
    # Daten aus dem Request Body holen (JSON Format)
    data = request.json
    email = data['email']
    username = email.split('@')[0]  # Username automatisch aus Email ableiten
    # Passwort hashen - niemals als reinen Text speichern!
    password = generate_password_hash(data['password'])

    # Email Validierung
    if not re.match(r'^[^@]+@[^@]+\.[^@]+$', email):
        return jsonify({"error": "Bitte eine gültige Email eingeben"}), 400

    # Neuen Nutzer erstellen und in der Datenbank speichern
    new_user = User(username=username, email=email, password=password)
    db.session.add(new_user)    # Nutzer zur Session hinzufügen
    db.session.commit()         # Änderungen in DB speichern

    # 201 = Created - Nutzer wurde erfolgreich erstellt
    return jsonify({"message": "User registered successfully", "user_id": new_user.id}), 201


@app.route('/login', methods=['POST'])
def login():
    # Daten aus dem Request Body holen
    data = request.json
    email = data['email']
    password = data['password']

    # Nutzer in der Datenbank anhand des Usernamens suchen
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


@app.route('/users/<user_id>', methods=['GET'])
def get_user(user_id):
    # Nutzer anhand der ID aus der Datenbank holen
    user = db.session.get(User, user_id)

    # Wenn Nutzer nicht gefunden → 404 Not Found
    if not user:
        return jsonify({"error": "User not found"}), 404

    # Nutzerdaten zurückgeben - Passwort wird NIEMALS zurückgegeben!
    return jsonify({
        "id": user.id,
        "username": user.username,
        "email": user.email
    }), 200


@app.route('/assets', methods=['POST'])
def add_asset():
    # Daten aus dem Request Body holen
    data = request.json
    name = data['name']
    symbol = data['symbol']
    asset_type = data['asset_type']
    currency = data['currency']

    # Neues Asset erstellen und in der Datenbank speichern
    new_asset = Asset(name=name, symbol=symbol, asset_type=asset_type, currency=currency)
    db.session.add(new_asset)
    db.session.commit()

    return jsonify({"message": "Asset successfully added"}), 201


@app.route('/users/<user_id>/assets', methods=['GET'])
def get_user_assets(user_id):
    """
    Alle Assets des Nutzers aus der user_asset Tabelle holen
    filter_by sucht alle Einträge mit der passenden user_id
    .all() gibt alle Ergebnisse als Liste zurück (nicht nur den ersten)
    """
    # Alle Assets des Nutzers aus der DB holen
    user_assets = UserAsset.query.filter_by(user_id=user_id).all()

    # Leere Liste erstellen - hier werden die Assets reingepackt
    result = []

    # Jeden Asset-Eintrag als Dictionary zur Liste hinzufügen
    for user_asset in user_assets:
        # Asset aus DB holen um Name und Symbol zu bekommen
        asset = db.session.get(Asset, user_asset.asset_id)

        if asset.asset_type == "stock" or asset.asset_type == "etf":
            current_price = get_stock_price(asset.symbol)
        elif asset.asset_type == "crypto":
            current_price = get_crypto_price(asset.symbol)
        elif asset.asset_type == "metal":
            current_price = get_metal_price(asset.symbol)

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
    # Daten aus dem Request Body holen
    data = request.json
    asset_id = data['asset_id']
    quantity = data['quantity']
    avg_buy_price = data['avg_buy_price']
    # Datum von String in Python datetime Objekt umwandeln
    bought_at = datetime.strptime(data['bought_at'], '%Y-%m-%d')
    status = data['status']

    # Neues UserAsset erstellen und in der Datenbank speichern
    user_assets = UserAsset(
        user_id=user_id,
        asset_id=asset_id,
        quantity=quantity,
        avg_buy_price=avg_buy_price,
        bought_at=bought_at,
        status=status
    )
    db.session.add(user_assets)
    db.session.commit()

    return jsonify({"message": "User asset successfully added"}), 201


@app.route('/assets/<asset_id>/prices', methods=['GET'])
def get_prices(asset_id):
    # Alle Preiseinträge für dieses Asset aus der DB holen
    prices = PriceHistory.query.filter_by(asset_id=asset_id).all()

    # Leere Liste erstellen
    result = []

    # Jeden Preis-Eintrag als Dictionary zur Liste hinzufügen
    for price in prices:
        result.append({
            "asset_id": price.asset_id,
            "date": price.date,
            "price": price.price,
            "currency": price.currency
        })

    return jsonify(result), 200


@app.route('/assets/<asset_id>/prices', methods=['POST'])
def add_prices(asset_id):
    # Daten aus dem Request Body holen
    data = request.json
    # Datum von String in Python datetime Objekt umwandeln
    date = datetime.strptime(data['date'], '%Y-%m-%d')
    price = data['price']
    currency = data['currency']

    # Neuen Preis in der Datenbank speichern
    new_price = PriceHistory(asset_id=asset_id, date=date, price=price, currency=currency)
    db.session.add(new_price)
    db.session.commit()

    return jsonify({"message": "Price successfully added"}), 201


@app.route('/watchlist', methods=['POST'])
def add_to_watchlist():
    # Daten aus dem Request Body holen
    data = request.json
    user_id = data['user_id']
    asset_id = data['asset_id']

    # Neuen Watchlist-Eintrag erstellen
    # added_at wird automatisch auf aktuelle Zeit gesetzt
    new_watchlist = Watchlist(user_id=user_id, asset_id=asset_id)
    db.session.add(new_watchlist)
    db.session.commit()

    return jsonify({"message": "Watchlist successfully updated"}), 201


@app.route('/users/<user_id>/watchlist', methods=['GET'])
def get_watchlist(user_id):
    # Alle Watchlist-Einträge des Nutzers holen
    assets = Watchlist.query.filter_by(user_id=user_id).all()

    result = []

    # Jeden Eintrag als Dictionary zur Liste hinzufügen
    for asset in assets:
        result.append({
            "user_id": asset.user_id,
            "asset_id": asset.asset_id
        })

    return jsonify(result), 200


@app.route('/users/<user_id>/watchlist/<asset_id>', methods=['DELETE'])
def delete_asset_from_watchlist(user_id, asset_id):
    # Eintrag in der DB suchen anhand user_id und asset_id
    watchlist_item = Watchlist.query.filter_by(user_id=user_id, asset_id=asset_id).first()

    # Wenn nicht gefunden → 404 Not Found
    if not watchlist_item:
        return jsonify({"error": "Item not found"}), 404

    # Eintrag löschen und Änderungen speichern
    db.session.delete(watchlist_item)
    db.session.commit()

    return jsonify({"message": "Watchlist successfully updated"}), 200


@app.route('/chat', methods=['POST'])
def chat():
    # Daten aus dem Request Body holen
    data = request.json
    user_id = data['user_id']
    message = data['message']

    # Nutzer aus DB holen um Profildaten zu erhalten
    user = db.session.get(User, user_id)

    # Bisherigen Chatverlauf aus DB holen
    # Wird ans LLM geschickt damit es den Kontext versteht
    chat_history = ChatHistory.query.filter_by(user_id=user_id).all()

    # Nutzerdaten vorbereiten - falls Felder leer sind "not specified" setzen
    if user.risk_profile:
        risk_profile = user.risk_profile
    else:
        risk_profile = "not specified"

    if user.investment_experience:
        investment_experience = user.investment_experience
    else:
        investment_experience = "not specified"

    if user.monthly_budget:
        monthly_budget = user.monthly_budget
    else:
        monthly_budget = "not specified"

    if user.investment_horizon:
        investment_horizon = user.investment_horizon
    else:
        investment_horizon = "not specified"

    # System Prompt als erstes Element der messages Liste
    # Definiert die Rolle und das Verhalten des LLM
    messages = [
        {
            "role": "system",
            "content": f"You are an experienced financial advisor. "
                       f"You explain financial concepts in a simple and understandable way. "
                       f"You analyze portfolios objectively. You never give direct buy or sell recommendations."
                       f"\n\nUser profile:"
                       f"\n- Risk profile: {risk_profile}"
                       f"\n- Investment experience: {investment_experience}"
                       f"\n- Monthly budget: {monthly_budget}"
                       f"\n- Investment horizon: {investment_horizon}"
                       f"\nIf certain user information is missing, mention that more accurate advice could be given with complete profile information."
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
        # LLM will ein Tool aufrufen!
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

        # Ergebnis zurück ans LLM schicken
        messages.append(response.choices[0].message)
        messages.append({
            "role": "tool",
            "tool_call_id": tool_call.id,
            "content": str(result)
        })

        # Finale Antwort vom LLM holen
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

    # LLM Antwort als JSON zurückgeben - 200 = OK
    return jsonify({"reply": llm_reply}), 200


@app.route('/chat/history/<user_id>', methods=['GET'])
def get_chat_history(user_id):
    # Chatverlauf aus DB holen
    chat_history = ChatHistory.query.filter_by(user_id=user_id).all()

    result = []
    for entry in chat_history:
        result.append({
            "role": entry.role,
            "message": entry.message
        })

    return jsonify(result), 200


@app.route('/users/<user_id>/settings', methods=['PUT'])
def settings(user_id):
    # Daten aus dem Request Body holen
    data = request.json
    risk_profile = data['risk_profile']
    investment_experience = data['investment_experience']
    monthly_budget = data['monthly_budget']
    investment_horizon = data['investment_horizon']

    # Bestehenden Nutzer aus DB holen
    user = db.session.get(User, user_id)

    # Wenn Nutzer nicht gefunden → 404 Not Found
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


@app.route('/portfolio/analyze', methods=['POST'])
def analyze_portfolio():
    # Daten aus dem Request Body holen
    data = request.json
    user_id = data['user_id']

    # Nutzer aus DB holen
    user = db.session.get(User, user_id)

    # Wenn Nutzer nicht gefunden → 404 Not Found
    if not user:
        return jsonify({"error": "User not found"}), 404

    # Alle Assets des Nutzers aus der DB holen
    user_assets = UserAsset.query.filter_by(user_id=user_id).all()

    # Nutzerdaten vorbereiten - falls Felder leer sind "not specified" setzen
    if user.risk_profile:
        risk_profile = user.risk_profile
    else:
        risk_profile = "not specified"

    if user.investment_experience:
        investment_experience = user.investment_experience
    else:
        investment_experience = "not specified"

    if user.monthly_budget:
        monthly_budget = user.monthly_budget
    else:
        monthly_budget = "not specified"

    if user.investment_horizon:
        investment_horizon = user.investment_horizon
    else:
        investment_horizon = "not specified"

    # Portfolio-Kontext aufbauen
    # Das LLM bekommt alle Assets mit Menge und Kaufpreis
    portfolio_context = ""
    for user_asset in user_assets:
        asset = db.session.get(Asset, user_asset.asset_id)

        if asset.asset_type == "stock" or asset.asset_type == "etf":
            current_price = get_stock_price(asset.symbol)
        elif asset.asset_type == "crypto":
            current_price = get_crypto_price(asset.symbol)
        elif asset.asset_type == "metal":
            current_price = get_metal_price(asset.symbol)

        current_value = user_asset.quantity * current_price

        portfolio_context += f"\n- {asset.name}: {user_asset.quantity} units" \
                             f"\n  Avg. buy price: {user_asset.avg_buy_price} {asset.currency}" \
                             f"\n  Current price: {current_price} {asset.currency}" \
                             f"\n  Current value: {current_value} {asset.currency}"

    # System Prompt für Portfolio-Analyse
    # Pydantic übernimmt das JSON Format - kein "respond in JSON" nötig!
    messages = [
        {
            "role": "system",
            "content": f"You are an experienced financial advisor. "
                       f"Always respond in German. "
                       f"Analyze the user's portfolio objectively. "
                       f"Never give direct buy or sell recommendations. "
                       f"\n\nUser profile:"
                       f"\n- Risk profile: {risk_profile}"
                       f"\n- Investment experience: {investment_experience}"
                       f"\n- Monthly budget: {monthly_budget}"
                       f"\n- Investment horizon: {investment_horizon}"
                       f"\n\nUser portfolio:{portfolio_context}"
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
    # .attribute statt ['key'] weil es ein Pydantic Objekt ist
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


@app.route('/dashboard')
def dashboard_page():
    return render_template('dashboard.html')

@app.route('/chat-page')
def chat_page():
    return render_template('chat.html')

@app.route('/analyse-page')
def analyse_page():
    return render_template('analyse.html')

@app.route('/watchlist-page')
def watchlist_page():
    return render_template('watchlist.html')

@app.route('/settings-page')
def settings_page():
    return render_template('settings.html')

if __name__ == '__main__':
    start_scheduler(app)
    app.run(debug=True)  # debug=True → automatischer Neustart bei Änderungen