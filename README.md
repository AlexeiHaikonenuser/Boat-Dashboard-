# Boat Dashboard

**English** | [Suomi](README.fi.md) | [Svenska](README.sv.md) | [Русский](README.ru.md) | [Deutsch](README.de.md)

A small web app for keeping a boat’s log in one place: trips and a public journal, motor hours, service, expenses, documents, sensors, and more than one boat if you need it.

It is a Flask application with SQLite. There is no separate database server. Each boat has its own database file, so a boat can be copied or backed up on its own.

**GitHub description (About):**  
Personal boat log for trips, motor hours, service, expenses, documents, and sensors. One command creates a working install. SQLite, no external database.

## What you can do

- Sign in with a username and password. An optional secure code can be required before the login page, and an admin can turn that step off.
- Keep more than one boat, and choose who may open each boat.
- Write a trip journal, share a post, and approve or delete public comments before they are shown.
- Record motor hours, service intervals, an onboard checklist, and passengers.
- Store expenses with receipt photos, documents, and tips.
- Show temperature, humidity, and bilge readings sent by a sensor.
- Switch the interface between English, Finnish, Swedish, Russian, and German.
- Photos are resized on upload (longest side 1600 px) so phone pictures do not fill the disk.

## Requirements

- Python 3.10 or newer
- pip

Check with:

```bash
python3 --version
```

On Windows you can use `py --version` or `python --version`.

## New installation

These steps create an empty dashboard with one boat and an admin account.  
**Do not do this if you already have a database you want to keep.** Use [Moving an existing boat](#moving-an-existing-boat) instead.

### 1. Get the files

```bash
git clone https://github.com/YOUR_USER/boat_dashboard.git
cd boat_dashboard
```

### 2. Create a virtual environment and install packages

macOS and Linux:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Windows (Command Prompt):

```bat
py -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Create the first database

```bash
python fresh_start.py
```

This deletes any `main.db` and `boats/` folder already in this directory, then creates:

| | |
|---|---|
| Secure code | `1234` |
| Username | `admin` |
| Password | `admin123` |
| Boat | My First Boat, assigned to `admin` |

Change the password after the first login. Add your own secure code under **Secure Codes**, then delete `1234`.

### 4. Allow login on your own computer

The app is set up for a site that uses HTTPS. On `http://localhost` the browser will not store the login cookie, so the password page reloads and you never get in.

Open `app.py` and, for a local test only, change:

```python
app.config['SESSION_COOKIE_SECURE'] = True
```

to:

```python
app.config['SESSION_COOKIE_SECURE'] = False
```

Put it back to `True` when the site is served over HTTPS.

### 5. Start

```bash
python app.py
```

Open [http://localhost:5000](http://localhost:5000).

## Daily use

1. Enter the secure code, if that step is turned on.
2. Sign in.
3. Choose a boat. The home page shows motor hours, sensors, and the boat gallery.
4. Use the side menu for the journal, motor history, service, onboard list, passengers, tips, expenses, documents, and boat info.

**Public journal.** In journal settings you can publish the journal. Visitors open it at:

```text
http://localhost:5000/<boat-name>/journal
```

Spaces in the boat name become hyphens, and the name is lower case. A boat named `My First Boat` is published at `/my-first-boat/journal`. Comments on a public post stay hidden until you open that post while signed in and press **Approve**.

**Secure code on or off.** Sign in as admin, open the user menu, then **Secure Codes**. The switch at the top turns the extra code on or off. Turning it off does not delete the codes.

**Add a person.** Admins can create users and assign them to a boat. A user only sees boats they are assigned to.

**Backup.** The admin boat page can download a zip of one boat’s database and uploaded files. Keep a copy of `main.db` as well. The zip does not contain user accounts.

## Moving an existing boat

Boat data is split across three places. For boat ID 2 the files are:

| Copy this | To the new folder | It contains |
|---|---|---|
| `main.db` | `main.db` | users, passwords, secure codes, the boat list |
| `boats/boat_2.db` | `boats/boat_2.db` | trips, motor hours, expenses, tips |
| `static/uploads/boat_2/` | `static/uploads/boat_2/` | photos, documents, receipts |

Do not rename `boat_2.db` to `boat_1.db`. The number is the boat ID, and photo paths inside the database use that number.

Then, in the new folder:

```bash
pip install -r requirements.txt
python migrate_db.py
python app.py
```

`migrate_db.py` adds any missing tables and columns. It does not delete trips, users, or boat IDs. The first run also writes `main.db.bak` and `boats/boat_2.db.bak`.

Do **not** run `fresh_start.py` on a folder that already contains your old `main.db`. That script removes the old databases.

Sign in with the old username, password, and secure code.

## Sensor readings

A device can post JSON to `POST /api/sensor`:

```json
{
  "boat_id": 2,
  "secret": "the-secret-set-for-this-boat",
  "temperature": 18.2,
  "humidity": 61,
  "bilge_level": 0
}
```

Set the secret in the admin boat page. A wrong secret is rejected.

## Project layout

```text
boat_dashboard/
├── app.py              # starts Flask
├── routes.py           # pages and the sensor API
├── models.py           # SQLite schema and upgrades
├── auth.py             # login checks
├── config.py           # paths, secret key, upload limits
├── translations.py     # English, Finnish, Swedish, Russian, German
├── utils.py            # motor hours and photo resizing
├── fresh_start.py      # empty install (deletes old data)
├── migrate_db.py       # upgrade an old database, keep the data
├── templates/          # pages
├── static/             # icons and, at runtime, uploads
├── boats/              # boat_1.db, boat_2.db, … (not in git)
└── main.db             # users and boat list (not in git)
```

## Configuration

`config.py` reads these settings:

| Setting | Meaning |
|---|---|
| `SECRET_KEY` | Set this environment variable on a server. Do not leave the default key on a public site. |
| `TIMEZONE` | Used for “now” in journals. Default `Europe/Helsinki`. |
| `ALLOWED_EXTENSIONS` | png, jpg, jpeg, gif, webp, pdf, gpx |
| `MAX_CONTENT_LENGTH` | 25 MB per upload, also set in `app.py` |

Generated files are listed in `.gitignore`: `*.db`, `boats/`, `static/uploads/`, `logs/`, and virtual environments. Do not commit them. They contain passwords, private trips, and photos.

## Production notes

- Run behind HTTPS and leave `SESSION_COOKIE_SECURE = True`.
- Change the admin password and the secure code.
- Set a long random `SECRET_KEY`.
- `python app.py` uses Flask’s development server (`debug=True`). For a public server, run it with a WSGI server such as gunicorn, behind nginx or Caddy.
- The development server listens on all interfaces, port 5000.

## License

MIT
