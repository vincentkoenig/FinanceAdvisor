"""
bank/client.py - Schmaler Client für die PSD2-Schnittstelle von Enable Banking.

Jede Anfrage trägt ein frisch signiertes JWT (RS256, kid = Application-ID), signiert
mit dem privaten Schlüssel der eigenen Enable-Banking-App. Konfiguration über
Umgebungsvariablen:
- ENABLE_BANKING_APP_ID        Application-ID aus dem Control Panel
- ENABLE_BANKING_PRIVATE_KEY   privater Schlüssel als PEM (Zeilenumbrüche dürfen als \\n stehen)
  oder ENABLE_BANKING_KEY_FILE Pfad zur PEM-Datei

Im "restricted mode" (kostenlos, für eigene Konten) liefert die API nur Daten von
Konten, die im Control Panel verknüpft wurden.
"""

import base64
import json
import os
import time

import requests
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

BASE_URL = 'https://api.enablebanking.com'
TIMEOUT = 30


class BankApiError(Exception):
    """Fehler der Schnittstelle. code ist der Fehlercode von Enable Banking, z.B. EXPIRED_SESSION."""

    def __init__(self, message, status=None, code=None):
        super().__init__(message)
        self.status = status
        self.code = code

    @property
    def session_expired(self):
        return self.status == 401 and self.code in ('EXPIRED_SESSION', 'SESSION_DOES_NOT_EXIST', 'REVOKED_SESSION')

    @property
    def rate_limited(self):
        return self.status == 429 or self.code == 'ASPSP_RATE_LIMIT_EXCEEDED'


def _b64(data):
    return base64.urlsafe_b64encode(data).rstrip(b'=').decode('ascii')


def _private_key_pem():
    pem = os.getenv('ENABLE_BANKING_PRIVATE_KEY')
    if pem:
        return pem.replace('\\n', '\n').encode('utf-8')
    path = os.getenv('ENABLE_BANKING_KEY_FILE')
    if path and os.path.exists(path):
        with open(path, 'rb') as handle:
            return handle.read()
    return None


def _describe_pem(pem):
    """Form des Schlüssels für die Fehlersuche, ohne etwas vom Inhalt zu verraten."""
    text = pem.decode('utf-8', 'replace')
    first = text.strip().splitlines()[0] if text.strip() else ''
    return (f'{len(text)} Zeichen, {text.count(chr(10))} Zeilenumbrüche, '
            f'beginnt mit "{first[:31]}", \\n im Text: {"ja" if chr(92) + "n" in text else "nein"}')


def configuration_error():
    """Warum der Bankabruf nicht nutzbar ist (Text) oder None, wenn alles passt."""
    if not is_configured():
        return None
    try:
        EnableBankingClient()
    except BankApiError as error:
        return str(error)
    return None


def is_configured():
    """Ist der Server für den Bankabruf eingerichtet (App-ID und Schlüssel vorhanden)?"""
    return bool(os.getenv('ENABLE_BANKING_APP_ID') and _private_key_pem())


class EnableBankingClient:

    def __init__(self, app_id=None, private_key_pem=None, session=None):
        self.app_id = app_id or os.getenv('ENABLE_BANKING_APP_ID')
        pem = private_key_pem or _private_key_pem()
        if not self.app_id or not pem:
            raise BankApiError('Der Bankabruf ist auf dem Server nicht eingerichtet')
        try:
            self._key = serialization.load_pem_private_key(pem, password=None)
        except (ValueError, TypeError) as error:
            raise BankApiError(f'Der private Schlüssel auf dem Server ist ungültig ({_describe_pem(pem)})') from error
        self._http = session or requests.Session()

    def _token(self):
        now = int(time.time())
        header = {'typ': 'JWT', 'alg': 'RS256', 'kid': self.app_id}
        payload = {'iss': 'enablebanking.com', 'aud': 'api.enablebanking.com', 'iat': now, 'exp': now + 3600}
        signing_input = f'{_b64(json.dumps(header).encode())}.{_b64(json.dumps(payload).encode())}'
        signature = self._key.sign(signing_input.encode('ascii'), padding.PKCS1v15(), hashes.SHA256())
        return f'{signing_input}.{_b64(signature)}'

    def _request(self, method, path, **kwargs):
        headers = {'Authorization': f'Bearer {self._token()}', 'Accept': 'application/json'}
        try:
            response = self._http.request(method, BASE_URL + path, headers=headers, timeout=TIMEOUT, **kwargs)
        except requests.RequestException as error:
            raise BankApiError(f'Enable Banking nicht erreichbar: {error.__class__.__name__}') from error
        if response.status_code >= 400:
            try:
                body = response.json()
            except ValueError:
                body = {}
            code = body.get('error') or body.get('code')
            message = body.get('message') or f'Enable Banking antwortet mit {response.status_code}'
            raise BankApiError(str(message)[:300], response.status_code, code)
        return response.json() if response.content else {}

    def aspsps(self, country='DE'):
        """Banken eines Landes: [{name, country, maximum_consent_validity, ...}]."""
        return self._request('GET', '/aspsps', params={'country': country}).get('aspsps', [])

    def start_authorization(self, aspsp_name, country, redirect_url, state, valid_until):
        """Anmeldung bei der Bank starten. Gibt die URL zurück, auf die der Browser muss."""
        body = {
            'access': {'valid_until': valid_until.isoformat()},
            'aspsp': {'name': aspsp_name, 'country': country},
            'state': state,
            'redirect_url': redirect_url,
            'psu_type': 'personal',
        }
        return self._request('POST', '/auth', json=body)

    def create_session(self, code):
        """Code vom Rücksprung gegen eine Sitzung mit Konten tauschen."""
        return self._request('POST', '/sessions', json={'code': code})

    def delete_session(self, session_id):
        return self._request('DELETE', f'/sessions/{session_id}')

    def balances(self, account_uid):
        return self._request('GET', f'/accounts/{account_uid}/balances').get('balances', [])

    def transactions(self, account_uid, date_from, strategy=None):
        """Alle Umsätze ab date_from, über alle Seiten (continuation_key)."""
        params = {'date_from': date_from.isoformat()}
        if strategy:
            params['strategy'] = strategy
        result = []
        for _ in range(100):  # Sicherung gegen eine endlose Folge von Seiten
            page = self._request('GET', f'/accounts/{account_uid}/transactions', params=params)
            result.extend(page.get('transactions') or [])
            key = page.get('continuation_key')
            if not key:
                break
            params['continuation_key'] = key
        return result
