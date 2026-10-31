"""
app.py - Einstiegspunkt der App.
Gunicorn startet im Container "gunicorn app:app" und importiert dafür das
Objekt app aus dieser Datei. Lokal startet "python app.py" den
Entwicklungsserver. Die eigentliche App wird im Paket fintrack/ gebaut.
"""

import os

from fintrack import create_app
from fintrack.jobs import start_scheduler

app = create_app()

# Scheduler starten - aktualisiert Preise, Dividenden und Insights automatisch.
# Läuft sowohl beim lokalen Start (python app.py) als auch wenn Gunicorn die
# App importiert (im Container). Mit SCHEDULER_ENABLED=0 lässt er sich abschalten,
# z.B. für einen zweiten lokalen Prozess.
if os.getenv('SCHEDULER_ENABLED', '1') == '1':
    start_scheduler(app)

if __name__ == '__main__':
    # Im Container läuft die App über Gunicorn, das diesen Block gar nicht
    # ausführt. Lokal steuern zwei Umgebungsvariablen den Start:
    # - FLASK_DEBUG=1 aktiviert den Debug-Modus (inkl. Werkzeug-Debugger)
    # - FLASK_HOST=0.0.0.0 macht den Server im lokalen Netzwerk erreichbar
    #   (z.B. vom Handy aus über die lokale IP), Standard ist nur dieser PC
    debug = os.getenv('FLASK_DEBUG') == '1'
    host = os.getenv('FLASK_HOST', '127.0.0.1')

    # Der Werkzeug-Debugger erlaubt das Ausführen von beliebigem Python-Code
    # im Browser - er darf deshalb nie im Netzwerk erreichbar sein
    if debug and host not in ('127.0.0.1', 'localhost'):
        print(f"WARNUNG: Debug-Modus wird deaktiviert, weil FLASK_HOST={host} nicht nur lokal ist.")
        debug = False

    app.run(debug=debug, host=host)
