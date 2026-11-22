# Boat Dashboard

[English](README.md) | [Suomi](README.fi.md) | **Svenska** | [Русский](README.ru.md) | [Deutsch](README.de.md)

En liten webbapp som samlar båtens logg på ett ställe: resor och en offentlig journal, motortimmar, service, utgifter, dokument, sensorer och fler än en båt om du behöver det.

Appen är byggd med Flask och SQLite. Ingen separat databasserver behövs. Varje båt har en egen databasfil, så en båt kan kopieras eller säkerhetskopieras för sig.

**GitHub-beskrivning (About):**  
Personlig båtlogg för resor, motortimmar, service, utgifter, dokument och sensorer. Ett kommando skapar en fungerande installation. SQLite, ingen extern databas.

## Det här kan du göra

- Logga in med användarnamn och lösenord. En valfri säkerhetskod kan krävas före inloggningssidan, och en administratör kan stänga av det steget.
- Ha fler än en båt och välja vem som får öppna varje båt.
- Skriva en resejournal, dela ett inlägg och godkänna eller ta bort offentliga kommentarer innan de visas.
- Anteckna motortimmar, serviceintervall, en checklista ombord och passagerare.
- Spara utgifter med kvittobilder, dokument och tips.
- Visa temperatur, luftfuktighet och slagvatten som en sensor skickar.
- Byta språk i gränssnittet: engelska, finska, svenska, ryska och tyska.
- Bilder förminskas vid uppladdning (längsta sidan högst 1600 px) så att telefonbilder inte fyller disken.

## Krav

- Python 3.10 eller nyare
- pip

Kontrollera med:

```bash
python3 --version
```

I Windows kan du använda `py --version` eller `python --version`.

## Ny installation

De här stegen skapar en tom panel med en båt och ett administratörskonto.  
**Gör inte detta om du redan har en databas som du vill behålla.** Använd då [Flytta en befintlig båt](#flytta-en-befintlig-båt).

### 1. Hämta filerna

```bash
git clone https://github.com/YOUR_USER/boat_dashboard.git
cd boat_dashboard
```

### 2. Skapa en virtuell miljö och installera paket

macOS och Linux:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Windows (kommandotolken):

```bat
py -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Skapa den första databasen

```bash
python fresh_start.py
```

Kommandot tar bort `main.db` och mappen `boats/` i den här katalogen och skapar sedan:

| | |
|---|---|
| Säkerhetskod | `1234` |
| Användarnamn | `admin` |
| Lösenord | `admin123` |
| Båt | My First Boat, tilldelad `admin` |

Byt lösenord efter första inloggningen. Lägg till en egen säkerhetskod under **Secure Codes** och ta sedan bort `1234`.

### 4. Tillåt inloggning på din egen dator

Appen är inställd för en webbplats med HTTPS. På `http://localhost` sparar webbläsaren inte inloggningskakan, så lösenordssidan laddas om och du kommer inte in.

Öppna `app.py` och ändra, bara för ett lokalt test:

```python
app.config['SESSION_COOKIE_SECURE'] = True
```

till:

```python
app.config['SESSION_COOKIE_SECURE'] = False
```

Sätt tillbaka värdet till `True` när webbplatsen körs över HTTPS.

### 5. Starta

```bash
python app.py
```

Öppna [http://localhost:5000](http://localhost:5000).

## Daglig användning

1. Ange säkerhetskoden om det steget är på.
2. Logga in.
3. Välj en båt. Startsidan visar motortimmar, sensorer och båtgalleriet.
4. Använd sidomenyn för journal, motorhistorik, service, checklista, passagerare, tips, utgifter, dokument och båtinformation.

**Offentlig journal.** I journalinställningarna kan du publicera journalen. Besökare öppnar den på:

```text
http://localhost:5000/<båtnamn>/journal
```

Mellanslag i båtnamnet blir bindestreck och namnet skrivs med små bokstäver. En båt som heter `My First Boat` publiceras på `/my-first-boat/journal`. Kommentarer på ett offentligt inlägg är dolda tills du öppnar inlägget inloggad och trycker på **Approve**.

**Säkerhetskod på eller av.** Logga in som administratör, öppna användarmenyn och välj **Secure Codes**. Reglaget högst upp slår på eller av extrakoden. Att stänga av den tar inte bort koderna.

**Lägg till en person.** Administratörer kan skapa användare och tilldela dem en båt. En användare ser bara båtar som hen är tilldelad.

**Säkerhetskopia.** På administratörens båtsida kan du ladda ner en zip med en båts databas och uppladdade filer. Spara också en kopia av `main.db`. Zip-filen innehåller inte användarkonton.

## Flytta en befintlig båt

Båtdata ligger på tre ställen. För båt med id 2 är filerna:

| Kopiera detta | Till den nya mappen | Innehåll |
|---|---|---|
| `main.db` | `main.db` | användare, lösenord, säkerhetskoder, båtlistan |
| `boats/boat_2.db` | `boats/boat_2.db` | resor, motortimmar, utgifter, tips |
| `static/uploads/boat_2/` | `static/uploads/boat_2/` | foton, dokument, kvitton |

Döp inte om `boat_2.db` till `boat_1.db`. Siffran är båtens id, och bildsökvägarna i databasen använder samma siffra.

I den nya mappen:

```bash
pip install -r requirements.txt
python migrate_db.py
python app.py
```

`migrate_db.py` lägger till tabeller och kolumner som saknas. Det tar inte bort resor, användare eller båt-id. Första körningen skriver också `main.db.bak` och `boats/boat_2.db.bak`.

Kör **inte** `fresh_start.py` i en mapp som redan innehåller din gamla `main.db`. Det skriptet tar bort de gamla databaserna.

Logga in med det gamla användarnamnet, lösenordet och säkerhetskoden.

## Sensorvärden

En enhet kan skicka JSON till `POST /api/sensor`:

```json
{
  "boat_id": 2,
  "secret": "the-secret-set-for-this-boat",
  "temperature": 18.2,
  "humidity": 61,
  "bilge_level": 0
}
```

Ange hemligheten på administratörens båtsida. Fel hemlighet avvisas.

## Projektets uppbyggnad

```text
boat_dashboard/
├── app.py              # startar Flask
├── routes.py           # sidor och sensor-API
├── models.py           # SQLite-schema och uppgraderingar
├── auth.py             # inloggningskontroller
├── config.py           # sökvägar, hemlig nyckel, uppladdningsgränser
├── translations.py     # engelska, finska, svenska, ryska, tyska
├── utils.py            # motortimmar och bildförminskning
├── fresh_start.py      # tom installation (tar bort gamla data)
├── migrate_db.py       # uppgradera en gammal databas, behåll data
├── templates/          # sidor
├── static/             # ikoner och, vid körning, uppladdningar
├── boats/              # boat_1.db, boat_2.db, … (inte i git)
└── main.db             # användare och båtlista (inte i git)
```

## Inställningar

`config.py` läser dessa inställningar:

| Inställning | Betydelse |
|---|---|
| `SECRET_KEY` | Sätt denna miljövariabel på en server. Lämna inte standardnyckeln på en offentlig webbplats. |
| `TIMEZONE` | Används för "nu" i journaler. Standard `Europe/Helsinki`. |
| `ALLOWED_EXTENSIONS` | png, jpg, jpeg, gif, webp, pdf, gpx |
| `MAX_CONTENT_LENGTH` | 25 MB per uppladdning, sätts också i `app.py` |

Skapade filer listas i `.gitignore`: `*.db`, `boats/`, `static/uploads/`, `logs/` och virtuella miljöer. Lägg inte in dem i git. De innehåller lösenord, privata resor och foton.

## Drift

- Kör bakom HTTPS och lämna `SESSION_COOKIE_SECURE = True`.
- Byt administratörens lösenord och säkerhetskoden.
- Sätt en lång slumpmässig `SECRET_KEY`.
- `python app.py` använder Flasks utvecklingsserver (`debug=True`). På en offentlig server kör appen med en WSGI-server, till exempel gunicorn, bakom nginx eller Caddy.
- Utvecklingsservern lyssnar på alla gränssnitt, port 5000.

## Licens

MIT
