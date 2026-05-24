from flask import Flask, request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash # für sicheres Passwort-Hashing
from models import db, User

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



if __name__ == '__main__':
    app.run(debug=True)