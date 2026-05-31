from flask import Flask, request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash # für sicheres Passwort-Hashing
from models import db, User, Asset, UserAsset, PriceHistory, Watchlist, ChatHistory
from datetime import datetime
from dotenv import load_dotenv
import os
from openai import OpenAI

load_dotenv()  # .env Datei laden!

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

app = Flask(__name__)

# Datenbank konfigurieren - Pfad zur SQLite Datei
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///finance_advisor.db'

# SQLAlchemy mit der App verbinden
db.init_app(app)

# Tabellen erstellen
with app.app_context():
    db.create_all()


@app.route('/')
def home():
    return "Hello to the FinanceAdvisor"


@app.route('/register', methods=['POST'])
def register():
    data = request.json # Daten aus dem Request holen
    username = data['username']
    email = data['email']
    password = generate_password_hash(data['password']) # Passwort hashen - niemals als reinen Text speichern!

    # Neuen Nutzer erstellen und in der Datenbank speichern
    new_user = User(username=username, email=email, password=password)
    db.session.add(new_user)
    db.session.commit()

    return jsonify({"message": "User registered successfully"}), 201


@app.route('/login', methods=['POST'])
def login():
    data = request.json  # Daten aus dem Request holen
    username = data['username']
    password = data['password']

    # Nutzer in der Datenbank suchen
    user = User.query.filter_by(username=username).first()

    # Wenn Nutzer nicht gefunden
    if not user:
        return jsonify({"error": "User not found"}), 404

    # Passwort überprüfen
    if not check_password_hash(user.password, password):
        return jsonify({"error": "Wrong password"}), 401

    # Wenn alles stimmt
    return jsonify({"message": "Login successful"}), 200


@app.route('/users/<user_id>', methods=['GET'])
def get_user(user_id):
    # Nutzer aus der Datenbank holen
    user = User.query.get(user_id)

    # Wenn Nutzer nicht gefunden
    if not user:
        return jsonify({"error": "User not found"}), 404

    # Nutzerdaten zurückgeben - Passwort wird nie zurückgegeben!
    return jsonify({
        "id": user.id,
        "username": user.username,
        "email": user.email
    }), 200


@app.route('/assets', methods=['POST'])
def add_asset():
    data = request.json  # Daten aus dem Request holen
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
    user_assets = UserAsset.query.filter_by(user_id=user_id).all()

    result = [] # Leere Liste erstellen - hier werden die Assets reingepackt

    for user_asset in user_assets: # Jeden Asset-Eintrag als Dictionary zur Liste hinzufügen
        result.append({"asset_id": user_asset.asset_id,
                       "quantity": user_asset.quantity,
                       "avg_buy_price": user_asset.avg_buy_price,
                       "bought_at": user_asset.bought_at,
                       "status": user_asset.status})

    return jsonify(result), 200


@app.route('/users/<user_id>/assets', methods=['POST'])
def add_user_asset(user_id):
    data = request.json  # Daten aus dem Request holen

    asset_id = data['asset_id']
    quantity = data['quantity']
    avg_buy_price = data['avg_buy_price']
    bought_at = datetime.strptime(data['bought_at'], '%Y-%m-%d')
    status = data['status']

    # Neues UserAsset erstellen und in der Datenbank speichern
    user_assets = UserAsset(user_id=user_id, asset_id=asset_id, quantity=quantity, avg_buy_price=avg_buy_price, bought_at=bought_at, status=status)
    db.session.add(user_assets)
    db.session.commit()

    return jsonify({"message": "User asset successfully added"}), 201


@app.route('/assets/<asset_id>/prices', methods=['GET'])
def get_prices(asset_id):

    prices = PriceHistory.query.filter_by(asset_id=asset_id).all()

    result = []  # Leere Liste erstellen - hier werden die Assets reingepackt

    for price in prices: # Jeden Asset-Eintrag als Dictionary zur Liste hinzufügen
        result.append({"asset_id": price.asset_id,
                       "date": price.date,
                       "price": price.price,
                       "currency": price.currency})

    return jsonify(result), 200


@app.route('/assets/<asset_id>/prices', methods=['POST'])
def add_prices(asset_id):
    data = request.json  # Daten aus dem Request holen

    date = datetime.strptime(data['date'], '%Y-%m-%d')
    price = data['price']
    currency = data['currency']

    # Neuen Preis eingeben und in der Datenbank speichern
    new_price = PriceHistory(asset_id=asset_id, date=date, price=price, currency=currency)
    db.session.add(new_price)
    db.session.commit()

    return jsonify({"message": "Price successfully added"}), 201


@app.route('/watchlist', methods=['POST'])
def add_to_watchlist():
    data = request.json  # Daten aus dem Request holen

    user_id = data['user_id']
    asset_id = data['asset_id']

    new_watchlist = Watchlist(user_id=user_id, asset_id=asset_id)
    db.session.add(new_watchlist)
    db.session.commit()

    return jsonify({"message": "Watchlist successfully updated"}), 201


@app.route('/users/<user_id>/watchlist', methods=['GET'])
def get_watchlist(user_id):
    assets = Watchlist.query.filter_by(user_id=user_id).all()

    result = []

    for asset in assets:
        result.append({"user_id": asset.user_id,
                       "asset_id": asset.asset_id,})

    return jsonify(result), 200


@app.route('/users/<user_id>/watchlist/<asset_id>', methods=['DELETE'])
def delete_asset_from_watchlist(user_id, asset_id):
    # Eintrag in der DB suchen
    watchlist_item = Watchlist.query.filter_by(user_id=user_id, asset_id=asset_id).first()

    # Wenn nicht gefunden
    if not watchlist_item:
        return jsonify({"error": "Item not found"}), 404

    # Löschen
    db.session.delete(watchlist_item)
    db.session.commit()

    return jsonify({"message": "Watchlist successfully updated"}), 201


@app.route('/chat', methods=['POST'])
def chat():
    data = request.json
    user_id = data['user_id']
    message = data['message']

    # Nutzer aus DB holen
    user = User.query.get(user_id)

    #  Bisherigen Chatverlauf aus DB holen
    chat_history = ChatHistory.query.filter_by(user_id=user_id).all()

    # Nutzerdaten vorbereiten
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

    # System Prompt als erstes Element
    messages = [
        {
            "role": "system",
            "content": "You are an experienced financial advisor. "
                       "You explain financial concepts in a simple and understandable way. "
                       "You analyze portfolios objectively. You never give direct buy or sell recommendations."
                       f"\n\nUser profile:"
                       f"\n- Risk profile: {risk_profile}"
                       f"\n- Investment experience: {investment_experience}"
                       f"\n- Monthly budget: {monthly_budget}"
                       f"\n- Investment horizon: {investment_horizon}"
                       f"If certain user information is missing, mention that more accurate advice could be given with complete profile information."
        }
    ]

    # In das Format bringen das OpenAI erwartet
    for entry in chat_history:
        messages.append({
            "role": entry.role,
            "content": entry.message
        })

    # Neue Nachricht hinzufügen
    messages.append({
        "role": "user",
        "content": message
    })

    # Nachricht ans LLM schicken
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        temperature=0.3
    )

    # Antwort des LLM aus dem Response-Objekt holen
    llm_reply = response.choices[0].message.content

    # Nutzer-Nachricht speichern
    new_user_message = ChatHistory(user_id=user_id, message=message, role="user")
    db.session.add(new_user_message)

    # LLM-Antwort speichern
    new_llm_reply = ChatHistory(user_id=user_id, message=llm_reply, role="assistant")
    db.session.add(new_llm_reply)

    db.session.commit()

    return jsonify({"reply": llm_reply}), 200


@app.route('/users/<user_id>/settings', methods=['PUT'])
def settings(user_id):
    data = request.json
    risk_profile = data['risk_profile']
    investment_experience = data['investment_experience']
    monthly_budget = data['monthly_budget']
    investment_horizon = data['investment_horizon']

    # Bestehenden Nutzer holen
    user = User.query.get(user_id)

    # Wenn Nutzer nicht gefunden
    if not user:
        return jsonify({"error": "User not found"}), 404

    # Felder aktualisieren
    user.risk_profile = risk_profile
    user.investment_experience = investment_experience
    user.monthly_budget = monthly_budget
    user.investment_horizon = investment_horizon

    db.session.commit()

    return jsonify({"message": "Settings successfully updated"}), 201

if __name__ == '__main__':
    app.run(debug=True)