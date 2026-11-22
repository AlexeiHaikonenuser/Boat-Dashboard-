# Boat Dashboard

[English](README.md) | [Suomi](README.fi.md) | [Svenska](README.sv.md) | [Русский](README.ru.md) | **Deutsch**

Eine kleine Web-App, die das Logbuch eines Bootes an einem Ort sammelt: Törns und ein öffentliches Journal, Motorstunden, Wartung, Ausgaben, Dokumente, Sensoren und mehr als ein Boot, wenn Sie das brauchen.

Die App ist mit Flask gebaut und nutzt SQLite. Ein eigener Datenbankserver ist nicht nötig. Jedes Boot hat eine eigene Datenbankdatei und lässt sich deshalb einzeln kopieren oder sichern.

**GitHub-Beschreibung (About):**  
Persönliches Bootslogbuch für Törns, Motorstunden, Wartung, Ausgaben, Dokumente und Sensoren. Ein Befehl erzeugt eine lauffähige Installation. SQLite, keine externe Datenbank.

## Was die App kann

- Anmeldung mit Benutzername und Passwort. Vor der Anmeldeseite kann ein Sicherheitscode verlangt werden, und ein Administrator kann diesen Schritt abschalten.
- Mehr als ein Boot führen und festlegen, wer welches Boot öffnen darf.
- Ein Törnjournal schreiben, einen Beitrag teilen und öffentliche Kommentare freigeben oder löschen, bevor sie sichtbar sind.
- Motorstunden, Wartungsintervalle, eine Checkliste an Bord und Passagiere festhalten.
- Ausgaben mit Belegfotos, Dokumente und Tipps speichern.
- Temperatur, Luftfeuchte und Bilge anzeigen, die ein Sensor sendet.
- Die Oberfläche auf Englisch, Finnisch, Schwedisch, Russisch oder Deutsch umschalten.
- Fotos werden beim Hochladen verkleinert (längste Seite höchstens 1600 px), damit Handybilder die Festplatte nicht füllen.

## Voraussetzungen

- Python 3.10 oder neuer
- pip

Prüfen mit:

```bash
python3 --version
```

Unter Windows können Sie `py --version` oder `python --version` verwenden.

## Neue Installation

Diese Schritte legen ein leeres Dashboard mit einem Boot und einem Administratorkonto an.  
**Tun Sie das nicht, wenn Sie eine vorhandene Datenbank behalten wollen.** Nutzen Sie dann [Ein vorhandenes Boot übernehmen](#ein-vorhandenes-boot-übernehmen).

### 1. Dateien holen

```bash
git clone https://github.com/YOUR_USER/boat_dashboard.git
cd boat_dashboard
```

### 2. Virtuelle Umgebung anlegen und Pakete installieren

macOS und Linux:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Windows (Eingabeaufforderung):

```bat
py -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Die erste Datenbank anlegen

```bash
python fresh_start.py
```

Das Skript löscht eine vorhandene `main.db` und den Ordner `boats/` in diesem Verzeichnis und legt danach an:

| | |
|---|---|
| Sicherheitscode | `1234` |
| Benutzername | `admin` |
| Passwort | `admin123` |
| Boot | My First Boat, `admin` zugewiesen |

Ändern Sie das Passwort nach der ersten Anmeldung. Legen Sie unter **Secure Codes** einen eigenen Code an und löschen Sie danach `1234`.

### 4. Anmeldung auf dem eigenen Rechner erlauben

Die App ist für eine Website mit HTTPS eingerichtet. Unter `http://localhost` speichert der Browser das Anmelde-Cookie nicht, die Passwortseite lädt neu und Sie kommen nicht hinein.

Öffnen Sie `app.py` und ändern Sie nur für einen lokalen Test:

```python
app.config['SESSION_COOKIE_SECURE'] = True
```

in:

```python
app.config['SESSION_COOKIE_SECURE'] = False
```

Setzen Sie den Wert wieder auf `True`, wenn die Website über HTTPS läuft.

### 5. Starten

```bash
python app.py
```

Öffnen Sie [http://localhost:5000](http://localhost:5000).

## Täglicher Gebrauch

1. Geben Sie den Sicherheitscode ein, wenn dieser Schritt eingeschaltet ist.
2. Melden Sie sich an.
3. Wählen Sie ein Boot. Die Startseite zeigt Motorstunden, Sensoren und die Bootgalerie.
4. Das Seitenmenü führt zu Journal, Motorhistorie, Wartung, Checkliste, Passagieren, Tipps, Ausgaben, Dokumenten und Bootsdaten.

**Öffentliches Journal.** In den Journaleinstellungen können Sie das Journal veröffentlichen. Besucher öffnen es unter:

```text
http://localhost:5000/<bootsname>/journal
```

Leerzeichen im Bootsnamen werden zu Bindestrichen, der Name wird klein geschrieben. Ein Boot namens `My First Boat` steht unter `/my-first-boat/journal`. Kommentare zu einem öffentlichen Beitrag bleiben verborgen, bis Sie den Beitrag angemeldet öffnen und **Approve** drücken.

**Sicherheitscode an oder aus.** Melden Sie sich als Administrator an, öffnen Sie das Benutzermenü und wählen Sie **Secure Codes**. Der Schalter oben schaltet den zusätzlichen Code ein oder aus. Ausschalten löscht die Codes nicht.

**Eine Person hinzufügen.** Administratoren können Benutzer anlegen und einem Boot zuweisen. Ein Benutzer sieht nur Boote, denen er zugewiesen ist.

**Sicherung.** Auf der Admin-Bootsseite können Sie eine Zip-Datei mit der Datenbank eines Boots und den hochgeladenen Dateien herunterladen. Bewahren Sie auch eine Kopie von `main.db` auf. Die Zip-Datei enthält keine Benutzerkonten.

## Ein vorhandenes Boot übernehmen

Die Bootsdaten liegen an drei Stellen. Für Boot-ID 2 sind das die Dateien:

| Kopieren | In den neuen Ordner | Inhalt |
|---|---|---|
| `main.db` | `main.db` | Benutzer, Passwörter, Sicherheitscodes, Bootsliste |
| `boats/boat_2.db` | `boats/boat_2.db` | Törns, Motorstunden, Ausgaben, Tipps |
| `static/uploads/boat_2/` | `static/uploads/boat_2/` | Fotos, Dokumente, Belege |

Benennen Sie `boat_2.db` nicht in `boat_1.db` um. Die Zahl ist die Boot-ID, und die Bildpfade in der Datenbank verwenden dieselbe Zahl.

Danach im neuen Ordner:

```bash
pip install -r requirements.txt
python migrate_db.py
python app.py
```

`migrate_db.py` ergänzt fehlende Tabellen und Spalten. Es löscht keine Törns, Benutzer oder Boot-IDs. Beim ersten Lauf schreibt es auch `main.db.bak` und `boats/boat_2.db.bak`.

Führen Sie **nicht** `fresh_start.py` in einem Ordner aus, der bereits Ihre alte `main.db` enthält. Das Skript löscht die alten Datenbanken.

Melden Sie sich mit dem alten Benutzernamen, Passwort und Sicherheitscode an.

## Sensorwerte

Ein Gerät kann JSON an `POST /api/sensor` senden:

```json
{
  "boat_id": 2,
  "secret": "the-secret-set-for-this-boat",
  "temperature": 18.2,
  "humidity": 61,
  "bilge_level": 0
}
```

Das Geheimnis stellen Sie auf der Admin-Bootsseite ein. Ein falsches Geheimnis wird abgelehnt.

## Aufbau des Projekts

```text
boat_dashboard/
├── app.py              # startet Flask
├── routes.py           # Seiten und Sensor-API
├── models.py           # SQLite-Schema und Upgrades
├── auth.py             # Anmeldeprüfungen
├── config.py           # Pfade, geheimer Schlüssel, Upload-Grenzen
├── translations.py     # Englisch, Finnisch, Schwedisch, Russisch, Deutsch
├── utils.py            # Motorstunden und Fotoverkleinerung
├── fresh_start.py      # leere Installation (löscht alte Daten)
├── migrate_db.py       # alte Datenbank aktualisieren, Daten behalten
├── templates/          # Seiten
├── static/             # Symbole und zur Laufzeit Uploads
├── boats/              # boat_1.db, boat_2.db, … (nicht in Git)
└── main.db             # Benutzer und Bootsliste (nicht in Git)
```

## Konfiguration

`config.py` liest diese Einstellungen:

| Einstellung | Bedeutung |
|---|---|
| `SECRET_KEY` | Setzen Sie diese Umgebungsvariable auf einem Server. Lassen Sie den Standardschlüssel nicht auf einer öffentlichen Website. |
| `TIMEZONE` | Wird für „jetzt“ in Journalen verwendet. Standard `Europe/Helsinki`. |
| `ALLOWED_EXTENSIONS` | png, jpg, jpeg, gif, webp, pdf, gpx |
| `MAX_CONTENT_LENGTH` | 25 MB pro Upload, auch in `app.py` gesetzt |

Erzeugte Dateien stehen in `.gitignore`: `*.db`, `boats/`, `static/uploads/`, `logs/` und virtuelle Umgebungen. Nehmen Sie sie nicht in Git auf. Sie enthalten Passwörter, private Törns und Fotos.

## Betrieb

- Hinter HTTPS betreiben und `SESSION_COOKIE_SECURE = True` lassen.
- Administratorpasswort und Sicherheitscode ändern.
- Einen langen zufälligen `SECRET_KEY` setzen.
- `python app.py` nutzt den Entwicklungsserver von Flask (`debug=True`). Für eine öffentliche Website die App mit einem WSGI-Server wie gunicorn hinter nginx oder Caddy betreiben.
- Der Entwicklungsserver lauscht auf allen Schnittstellen, Port 5000.

## Lizenz

MIT
