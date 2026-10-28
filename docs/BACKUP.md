# Backups und Wiederherstellung

Die Produktionsdatenbank (Neon) wird jede Nacht automatisch gesichert. Der
Workflow `.github/workflows/backup.yml` erledigt das in vier Schritten:

1. **Sichern** mit `pg_dump`: alle Tabellen und Einträge.
2. **Verschlüsseln** mit GPG (AES-256). Ohne Verschlüsselung wären die
   Sicherungen in diesem öffentlichen Repository für jeden angemeldeten
   GitHub-Nutzer herunterladbar.
3. **Ablegen** als Artefakt des Workflow-Laufs, 90 Tage lang.
4. **Wiederherstellung testen**: Die Sicherung wird entschlüsselt, in eine
   leere Datenbank eingespielt und die Zahl der Einträge pro Tabelle mit dem
   Original verglichen. Stimmt etwas nicht, wird der Lauf rot und GitHub
   schickt eine E-Mail.

## Einrichtung

Unter **Settings → Secrets and variables → Actions → New repository secret**
zwei Secrets anlegen:

| Name | Inhalt |
|---|---|
| `BACKUP_DATABASE_URL` | Connection String der Neon-Datenbank, derselbe Wert wie `DATABASE_URL` auf Render |
| `BACKUP_PASSPHRASE` | Langes Passwort für die Verschlüsselung, im Passwortmanager ablegen |

> **Ohne `BACKUP_PASSPHRASE` lassen sich die Sicherungen nicht mehr öffnen.**
> Das Passwort muss außerhalb von GitHub aufbewahrt werden.

Ändert sich die Datenbank (z.B. Umzug zu einem anderen Anbieter), muss
`BACKUP_DATABASE_URL` mit angepasst werden.

## Sicherung von Hand starten

**Actions → Datenbank-Backup → Run workflow**. Vor jedem größeren Umbau an der
Datenbank (Migration, Umzug) eine Sicherung starten und abwarten, bis der Lauf
grün ist.

## Wiederherstellen

Benötigt werden `gpg` (in Git für Windows enthalten, in Git Bash nutzbar) und
die PostgreSQL-Kommandozeilenwerkzeuge (`pg_restore`, `psql`) in mindestens der
Version des Datenbankservers. Unter Windows reicht bei der Installation von
postgresql.org die Komponente „Command Line Tools“.

**1. Sicherung herunterladen**

Im Browser: **Actions → Datenbank-Backup →** gewünschten Lauf öffnen **→
Artifacts** und die Datei herunterladen und entpacken. Oder mit der GitHub-CLI:

```bash
gh run list --workflow backup.yml --limit 5
gh run download <RUN-ID>
```

**2. Entschlüsseln** (fragt nach `BACKUP_PASSPHRASE`)

```bash
gpg --decrypt --output fintrack.dump fintrack-JJJJ-MM-TT_HHMM.dump.gpg
```

**3. In eine leere Datenbank einspielen**

Immer in eine **neue, leere** Datenbank einspielen, z.B. ein neues
Neon-Projekt oder einen neuen Neon-Branch, nie über eine Datenbank mit Daten.

```bash
pg_restore --no-owner --no-privileges --exit-on-error \
  --dbname="postgresql://NUTZER:PASSWORT@HOST/DATENBANK?sslmode=require" \
  fintrack.dump
```

**4. Umschalten**

`DATABASE_URL` auf Render und das Secret `BACKUP_DATABASE_URL` auf die neue
Datenbank setzen und auf Render neu deployen.

**5. Aufräumen**

Die entschlüsselte `fintrack.dump` enthält alle Daten im Klartext und sollte
danach gelöscht werden.

## Gut zu wissen

- **Pause nach 60 Tagen:** GitHub schaltet zeitgesteuerte Workflows in
  öffentlichen Repositories ab, wenn es 60 Tage lang keine Commits gab. GitHub
  schickt vorher eine E-Mail. Dann unter **Actions → Datenbank-Backup** auf
  „Enable workflow“ klicken.
- **Fehlermeldungen:** Schlägt ein nächtlicher Lauf fehl, schickt GitHub eine
  E-Mail an die Person, die den Workflow zuletzt geändert hat.
- **Die Logs sind öffentlich.** Der Workflow gibt deshalb nur Tabellennamen und
  die Größe der Sicherung aus, keine Inhalte und keine Zeilenzahlen.
