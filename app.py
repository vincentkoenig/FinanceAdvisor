from flask import Flask, request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash # für sicheres Passwort-Hashing
from models import db, User, Asset, UserAsset, PriceHistory
from datetime import datetime

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


if __name__ == '__main__':
    app.run(debug=True)