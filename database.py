import sqlite3

# Verbindung zur Datenbank herstellen
# Wenn die Datei nicht existiert, wird sie automatisch erstellt
connection = sqlite3.connect("finance_advisor.db")

# Cursor erstellen - er führt die SQL Befehle aus
cursor = connection.cursor()

# user Tabelle erstellen
# Speichert alle registrierten Nutzer mit ihren Profildaten
cursor.execute("""
    CREATE TABLE IF NOT EXISTS user (
        id INTEGER PRIMARY KEY AUTOINCREMENT,  
        username VARCHAR,                       
        email VARCHAR,                          
        age INTEGER,                           
        gender VARCHAR,                         
        risk_profile VARCHAR,                   
        investment_experience VARCHAR,          
        monthly_budget FLOAT,                   
        investment_horizon VARCHAR,             
        created_at TIMESTAMP                    
    )
""")

# asset Tabelle erstellen
# Speichert alle verfügbaren Finanzprodukte unabhängig vom Nutzer
# z.B. Apple existiert einmal hier, egal wie viele Nutzer Apple besitzen
cursor.execute("""
    CREATE TABLE IF NOT EXISTS asset (
        id INTEGER PRIMARY KEY AUTOINCREMENT,  
        name VARCHAR,                          
        symbol VARCHAR,                        
        asset_type VARCHAR,                    
        currency VARCHAR                       
    )
""")

# user_asset Tabelle erstellen
# Junction Table - verbindet user und asset (Many-to-Many Beziehung)
# Beantwortet: Welcher Nutzer besitzt welches Asset und wie viel?
cursor.execute("""
    CREATE TABLE IF NOT EXISTS user_asset (
        id INTEGER PRIMARY KEY AUTOINCREMENT,  
        user_id INTEGER,                       
        asset_id INTEGER,                      
        quantity FLOAT,                        
        avg_buy_price FLOAT,                   
        bought_at TIMESTAMP,                   
        status VARCHAR                         
    )
""")

# price_history Tabelle erstellen
# Speichert täglich die Preise aller Assets
# So kann man die Preisentwicklung über Zeit verfolgen
cursor.execute("""
    CREATE TABLE IF NOT EXISTS price_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,  
        asset_id INTEGER,                      
        date DATE,                             
        price FLOAT,                           
        currency VARCHAR                       
    )
""")

# chat_history Tabelle erstellen
# Speichert den gesamten Chatverlauf zwischen Nutzer und LLM
# Wird benötigt damit das LLM den Kontext des Gesprächs versteht
cursor.execute("""
    CREATE TABLE IF NOT EXISTS chat_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,  
        user_id INTEGER,                       
        message TEXT,                          
        role VARCHAR,                          
        created_at TIMESTAMP                   
    )
""")

# watchlist Tabelle erstellen
# Speichert Assets die der Nutzer beobachtet aber noch nicht besitzt
cursor.execute("""
    CREATE TABLE IF NOT EXISTS watchlist (
        id INTEGER PRIMARY KEY AUTOINCREMENT,  
        user_id INTEGER,                       
        asset_id INTEGER,                      
        added_at TIMESTAMP                     
    )
""")

# Änderungen speichern
# Ohne commit() gehen alle Änderungen verloren - wie eine Word Datei ohne speichern!
connection.commit()

# Verbindung zur Datenbank schließen
connection.close()