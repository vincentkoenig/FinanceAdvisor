"""
email_service.py - E-Mail-Versand über Resend, für die
Registrierungs-Verifizierung. Nutzt die Resend-Test-Domain
(onboarding@resend.dev), solange keine eigene Domain verifiziert ist -
damit können E-Mails aktuell nur an die eigene, bei Resend registrierte
Adresse verschickt werden.
"""

import os
import random
import resend

resend.api_key = os.getenv("RESEND_API_KEY")


def generate_verification_code():
    """Generiert einen 6-stelligen, numerischen Verifizierungscode"""
    return str(random.randint(100000, 999999))


def send_verification_email(to_email, code):
    """
    Verschickt eine E-Mail mit dem Verifizierungscode.
    Gibt True bei Erfolg zurück, False bei einem Fehler.
    """
    try:
        resend.Emails.send({
            "from": "FinTrack <onboarding@resend.dev>",
            "to": [to_email],
            "subject": "Dein Verifizierungscode für FinTrack",
            "html": (
                f"<p>Willkommen bei FinTrack!</p>"
                f"<p>Dein Verifizierungscode lautet:</p>"
                f"<h2 style='letter-spacing: 4px;'>{code}</h2>"
                f"<p>Der Code ist 15 Minuten lang gültig.</p>"
            )
        })
        return True
    except Exception as e:
        print(f"Error sending verification email: {e}")
        return False