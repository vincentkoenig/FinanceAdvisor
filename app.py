from flask import Flask, request, jsonify
from werkzeug.security import generate_password_hash
from models import db, User

app = Flask(__name__)

# Datenbank konfigurieren
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
    password = generate_password_hash(data['password'])

    new_user = User(username=username, email=email, password=password)
    db.session.add(new_user)
    db.session.commit()

    return jsonify({"message": "User registered successfully"}), 201


if __name__ == '__main__':
    app.run(debug=True)