"""
spa.py - Liefert das neue React-Frontend (frontend/dist) unter /app aus.
Während des Umbaus laufen die bisherigen Seiten unter / weiter.

- Dateien mit Hash im Namen (/app/assets/...) ändern sich nie und dürfen
  ein Jahr im Browser-Cache bleiben.
- Der Service Worker (sw.js) und das Manifest werden nie gecacht, damit der
  Browser ein Update sofort bemerkt.
- Jede andere Adresse unter /app bekommt index.html (das Frontend entscheidet
  selbst, welche Seite es zeigt) und wird nie gecacht, damit nach einem
  Deploy sofort die neue Version lädt.
- Die Anmeldung prüft das Frontend über /api/v1/me; die Dateien selbst
  enthalten keine Nutzerdaten und sind deshalb ohne Login abrufbar.
"""

import os

from flask import Blueprint, current_app, redirect, send_from_directory

bp = Blueprint('spa', __name__)

ONE_YEAR = 365 * 24 * 60 * 60

# Python kennt .webmanifest nicht überall; Browser erwarten diesen Typ
MIMETYPES = {'.webmanifest': 'application/manifest+json'}
NEVER_CACHED = {'sw.js', 'manifest.webmanifest'}


def _dist():
    return current_app.config['FRONTEND_DIST']


@bp.route('/app')
def app_root():
    return redirect('/app/', code=308)


@bp.route('/app/', defaults={'path': ''})
@bp.route('/app/<path:path>')
def frontend(path):
    dist = _dist()
    if path and os.path.isfile(os.path.join(dist, path)):
        # send_from_directory verhindert Ausbrüche aus dem Ordner (../)
        max_age = ONE_YEAR if path.startswith('assets/') else 0
        mimetype = MIMETYPES.get(os.path.splitext(path)[1])
        response = send_from_directory(dist, path, max_age=max_age, mimetype=mimetype)
        if max_age:
            response.cache_control.immutable = True
        if path in NEVER_CACHED:
            response.cache_control.no_cache = True
        return response

    if path.startswith('assets/'):
        # Eine fehlende gehashte Datei ist ein echter 404, nicht die Startseite
        return 'Nicht gefunden', 404

    if not os.path.isfile(os.path.join(dist, 'index.html')):
        return ('Das neue Frontend ist noch nicht gebaut. Lokal: "npm run build" im Ordner frontend.',
                503, {'Content-Type': 'text/plain; charset=utf-8'})

    response = send_from_directory(dist, 'index.html', max_age=0)
    response.cache_control.no_cache = True
    return response
