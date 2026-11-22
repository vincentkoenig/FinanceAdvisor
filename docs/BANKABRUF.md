# Bankabruf einrichten (Enable Banking)

FinTrack holt Kontoumsätze und Kontostand jede Nacht direkt von der Bank, über die
PSD2-Schnittstelle von [Enable Banking](https://enablebanking.com). Für die eigenen Konten
reicht der kostenlose „restricted mode“: Die eigene App bei Enable Banking darf dann nur
Konten lesen, die du im Control Panel verknüpft hast. FinTrack kann nur lesen, nie überweisen.

## 1. App bei Enable Banking anlegen

1. Im [Control Panel](https://enablebanking.com/cp/applications) registrieren und eine neue
   Anwendung anlegen, Umgebung **Production**.
2. Den privaten Schlüssel im Browser erzeugen lassen und die `.pem`-Datei speichern
   (oder selbst: `openssl genrsa -out private.key 4096` und das Zertifikat hochladen).
3. Als Rücksprung-Adresse (Redirect URL) genau diese eintragen:
   `https://fintrack.vincentkoenig.ai/api/v1/bank/callback`
   Dieselbe Adresse zeigt FinTrack in den Einstellungen unter „Bankabruf“, solange der Server
   noch nicht eingerichtet ist.
4. Die Application-ID notieren.
5. **Activate by linking accounts:** im Control Panel das HVB-Konto verknüpfen. Erst dann ist
   die App aktiv und liefert Daten für dieses Konto.

## 2. Server einrichten

Am einfachsten vom eigenen PC aus (trägt beides ein und startet FinTrack neu):

```powershell
powershell -ExecutionPolicy Bypass -File deploy\set-bank-key.ps1 -KeyFile "C:\Pfad\zur\datei.pem"
```

Oder von Hand in `/opt/fintrack/.env` (siehe `deploy/README.md`) ergänzen:

```
ENABLE_BANKING_APP_ID=deine-application-id
ENABLE_BANKING_PRIVATE_KEY=-----BEGIN PRIVATE KEY-----\nMIIJ...\n-----END PRIVATE KEY-----\n
```

Der Schlüssel muss in **einer** Zeile stehen, Zeilenumbrüche als `\n`. Umwandeln:

```bash
awk 'NF {sub(/\r/, ""); printf "%s\\n", $0}' private.pem
```

Alternativ die Datei auf den Server legen, in den Container einbinden und
`ENABLE_BANKING_KEY_FILE=/pfad/im/container/private.pem` setzen. Nur falls FinTrack hinter
einem Proxy die eigene Adresse falsch erkennt: `ENABLE_BANKING_REDIRECT_URL` mit der Adresse
aus Schritt 1.3 setzen.

Danach neu ausrollen: `sh /opt/fintrack/src/deploy/server-deploy.sh`

## 3. In FinTrack verbinden

Einstellungen → **Bankabruf** → Bank wählen (HypoVereinsbank ist vorausgewählt) →
**Bei der Bank anmelden**. Du meldest dich auf der Seite der HVB an und bestätigst in der
HVB-App. Danach springt die Bank zu FinTrack zurück.

- **Erster Abruf:** ab dem Tag deiner letzten importierten Buchung (CSV/PDF), damit nichts
  doppelt kommt; ohne frühere Importe 89 Tage zurück.
- **Danach:** jede Nacht um 22:30 Uhr im täglichen Lauf, zusätzlich „Jetzt abrufen“.
- **Buchen:** Umsätze mit bekanntem Empfänger oder passender Regel bucht FinTrack selbst.
  Was in einer wiederkehrenden Buchung steckt (Miete, Gehalt), wird nicht noch einmal gebucht.
  Der Rest wartet im Haushaltsbuch unter „Prüfen“.
- **Kontostand:** Der Saldo der Bank wird jeden Tag als Kontostand eingetragen.
- **Freigabe:** gilt bei den meisten Banken bis zu 180 Tage. 7 Tage und 1 Tag vorher kommt eine
  Push-Meldung, in den Einstellungen dann „Erneuern“. Auswahl und Abrufstand der Konten bleiben.
