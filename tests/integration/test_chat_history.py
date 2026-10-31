"""
test_chat_history.py - Chatverlauf abrufen und mit "Neuer Chat" löschen.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from fintrack.extensions import db
from fintrack.models import ChatHistory


def _add_messages(user, *texts):
    for i, text in enumerate(texts):
        db.session.add(ChatHistory(user_id=user.id, role='user' if i % 2 == 0 else 'assistant', message=text))
    db.session.commit()


class TestNewChat:

    def test_delete_clears_own_history(self, make_user, login_client):
        user = make_user('a@test.com')
        _add_messages(user, 'Frage', 'Antwort')
        client = login_client('a@test.com')

        response = client.delete('/api/v1/me/chat/history')

        assert response.status_code == 200
        assert response.get_json() == {'deleted': 2}
        assert client.get('/api/v1/me/chat/history').get_json() == []

    def test_other_users_keep_their_history(self, make_user, login_client):
        a = make_user('a@test.com')
        b = make_user('b@test.com')
        _add_messages(a, 'Frage von A')
        _add_messages(b, 'Frage von B', 'Antwort an B')

        login_client('a@test.com').delete('/api/v1/me/chat/history')

        assert ChatHistory.query.filter_by(user_id=b.id).count() == 2
        assert ChatHistory.query.filter_by(user_id=a.id).count() == 0

    def test_empty_history_is_fine(self, make_user, login_client):
        make_user('a@test.com')

        response = login_client('a@test.com').delete('/api/v1/me/chat/history')

        assert response.get_json() == {'deleted': 0}

    def test_requires_login(self, app):
        assert app.test_client().delete('/api/v1/me/chat/history').status_code == 401
