"""
test_spa.py - Auslieferung des React-Frontends unter /app: Startseite für
jede Frontend-Adresse, langer Cache nur für gehashte Dateien, kein Zugriff
außerhalb des Build-Ordners und ein klarer Hinweis, wenn nicht gebaut wurde.
"""

import pytest

from fintrack import create_app


@pytest.fixture
def dist(tmp_path):
    """Ein kleiner Build-Ordner wie nach "npm run build"."""
    (tmp_path / 'assets').mkdir()
    (tmp_path / 'index.html').write_text('<!doctype html><title>FinTrack</title>', encoding='utf-8')
    (tmp_path / 'assets' / 'index-abc123.js').write_text('console.log(1)', encoding='utf-8')
    (tmp_path / 'icon.svg').write_text('<svg/>', encoding='utf-8')
    (tmp_path / 'sw.js').write_text('// sw', encoding='utf-8')
    (tmp_path / 'manifest.webmanifest').write_text('{}', encoding='utf-8')
    return tmp_path


@pytest.fixture
def client(dist):
    return create_app('testing', {'FRONTEND_DIST': str(dist)}).test_client()


def test_app_without_slash_redirects(client):
    response = client.get('/app')
    assert response.status_code == 308
    assert response.headers['Location'].endswith('/app/')


@pytest.mark.parametrize('path', ['/app/', '/app/login', '/app/portfolio/positionen'])
def test_every_frontend_url_gets_index_without_cache(client, path):
    response = client.get(path)
    assert response.status_code == 200
    assert b'<title>FinTrack</title>' in response.data
    assert 'no-cache' in response.headers['Cache-Control']


def test_hashed_assets_are_cached_for_a_year(client):
    response = client.get('/app/assets/index-abc123.js')
    assert response.status_code == 200
    assert 'max-age=31536000' in response.headers['Cache-Control']
    assert 'immutable' in response.headers['Cache-Control']


def test_other_files_are_not_cached_long(client):
    response = client.get('/app/icon.svg')
    assert response.status_code == 200
    assert 'max-age=31536000' not in response.headers.get('Cache-Control', '')


@pytest.mark.parametrize('path', ['/app/sw.js', '/app/manifest.webmanifest'])
def test_service_worker_and_manifest_are_never_cached(client, path):
    """Sonst bemerkt der Browser ein Update der App erst nach Tagen"""
    response = client.get(path)
    assert response.status_code == 200
    assert 'no-cache' in response.headers['Cache-Control']


def test_manifest_has_its_media_type(client):
    assert client.get('/app/manifest.webmanifest').mimetype == 'application/manifest+json'


def test_missing_asset_is_404_not_index(client):
    assert client.get('/app/assets/gibt-es-nicht.js').status_code == 404


def test_no_access_outside_build_folder(client, dist):
    (dist.parent / 'geheim.txt').write_text('geheim', encoding='utf-8')
    response = client.get('/app/../geheim.txt')
    assert b'geheim' not in response.data


def test_hint_when_frontend_not_built(tmp_path):
    client = create_app('testing', {'FRONTEND_DIST': str(tmp_path / 'fehlt')}).test_client()
    response = client.get('/app/')
    assert response.status_code == 503
    assert 'npm run build' in response.get_data(as_text=True)


def test_api_is_not_affected(client):
    """Die API antwortet weiter mit JSON, nicht mit der Frontend-Startseite."""
    response = client.get('/api/v1/me')
    assert response.status_code == 401
    assert response.is_json
