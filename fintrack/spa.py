"""
spa.py - Liefert das React-Frontend (frontend/dist) unter /app aus.

- / und die Adressen der früheren Seiten (/home-page, /portfolio-page, ...)
  leiten auf die passende Seite unter /app weiter, damit Lesezeichen und eine
  früher installierte App weiter funktionieren.

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


# Frühere Seiten -> Seite im React-Frontend. 302 statt 301, damit Browser die
# Weiterleitung nicht für immer speichern, falls das Frontend einmal unter / zieht.
LEGACY_PAGES = {
    '/': '/app/',
    '/home-page': '/app/',
    '/portfolio-page': '/app/portfolio',
    '/budget-page': '/app/budget',
    '/chat-page': '/app/chat',
    '/analyse-page': '/app/analyse',
    '/settings-page': '/app/settings',
}


def _legacy_redirect(target):
    return lambda: redirect(target, code=302)


for _path, _target in LEGACY_PAGES.items():
    bp.add_url_rule(_path, endpoint='legacy_' + (_path.strip('/').replace('-', '_') or 'root'),
                    view_func=_legacy_redirect(_target))


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
