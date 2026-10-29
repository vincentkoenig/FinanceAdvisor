"""
test_admin_routes.py - Integration Tests für die internen Endpoints
(/update-prices, /check-dividends, /generate-insights, /run-daily-jobs). Diese dürfen
nur mit dem richtigen Schlüssel aus ADMIN_API_KEY aufrufbar sein,
weil sie sonst jeder auslösen und z.B. OpenAI-Kosten verursachen könnte.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest


ADMIN_ROUTES = ['/api/v1/admin/update-prices', '/api/v1/admin/check-dividends',
                '/api/v1/admin/generate-insights', '/api/v1/admin/run-daily-jobs']


@pytest.fixture
def mock_admin_jobs(mocker):
    """Ersetzt den Job-Start durch einen Mock, damit die Tests keine
    echten Kurs-APIs oder OpenAI aufrufen."""
    return mocker.patch('fintrack.admin.routes.start_job', return_value=True)


class TestAdminRoutes:
    """Integration Tests für den Schutz der internen Endpoints"""

    @pytest.mark.parametrize('route', ADMIN_ROUTES)
    def test_rejects_request_without_key(self, app, mock_admin_jobs, monkeypatch, route):
        """Ohne X-Admin-Key-Header wird der Aufruf mit 403 abgelehnt"""
        monkeypatch.setenv('ADMIN_API_KEY', 'geheim')
        client = app.test_client()

        response = client.post(route)

        assert response.status_code == 403

    @pytest.mark.parametrize('route', ADMIN_ROUTES)
    def test_rejects_wrong_key(self, app, mock_admin_jobs, monkeypatch, route):
        """Ein falscher Schlüssel wird mit 403 abgelehnt"""
        monkeypatch.setenv('ADMIN_API_KEY', 'geheim')
        client = app.test_client()

        response = client.post(route, headers={'X-Admin-Key': 'falsch'})

        assert response.status_code == 403

    @pytest.mark.parametrize('route', ADMIN_ROUTES)
    def test_locked_when_no_key_configured(self, app, mock_admin_jobs, monkeypatch, route):
        """Ist ADMIN_API_KEY nicht gesetzt, sind die Endpoints komplett
        gesperrt - auch ein leerer Header öffnet sie nicht"""
        monkeypatch.delenv('ADMIN_API_KEY', raising=False)
        client = app.test_client()

        response = client.post(route, headers={'X-Admin-Key': ''})

        assert response.status_code == 403

    @pytest.mark.parametrize('route', ADMIN_ROUTES)
    def test_accepts_correct_key(self, app, mock_admin_jobs, monkeypatch, route):
        """Mit dem richtigen Schlüssel startet der Job im Hintergrund (202)"""
        monkeypatch.setenv('ADMIN_API_KEY', 'geheim')
        client = app.test_client()

        response = client.post(route, headers={'X-Admin-Key': 'geheim'})

        assert response.status_code == 202
        mock_admin_jobs.assert_called_once()


class TestVerificationCode:
    """Unit Tests für den Verifizierungscode"""

    def test_code_has_six_digits(self):
        """Der Code ist immer genau 6 Ziffern lang, auch über viele Durchläufe"""
        from fintrack.auth.email import generate_verification_code

        for _ in range(500):
            code = generate_verification_code()
            assert len(code) == 6
            assert code.isdigit()
