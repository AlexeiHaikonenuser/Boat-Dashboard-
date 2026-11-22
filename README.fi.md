# Boat Dashboard

[English](README.md) | **Suomi** | [Svenska](README.sv.md) | [Русский](README.ru.md) | [Deutsch](README.de.md)

Pieni verkkosovellus, johon veneen loki kootaan yhteen paikkaan: matkat ja julkinen päiväkirja, moottoritunnit, huolto, kulut, asiakirjat, anturit ja useampi vene, jos niitä on.

Sovellus on tehty Flaskilla ja käyttää SQLite-tietokantaa. Erillistä tietokantapalvelinta ei tarvita. Jokaisella veneellä on oma tietokantatiedosto, joten veneen voi kopioida tai varmuuskopioida erikseen.

**GitHub-kuvaus (About):**  
Henkilökohtainen veneloki matkoille, moottoritunneille, huollolle, kuluille, asiakirjoille ja antureille. Yksi komento luo toimivan asennuksen. SQLite, ei ulkoista tietokantaa.

## Mitä sovelluksella voi tehdä

- Kirjaudu käyttäjätunnuksella ja salasanalla. Ennen kirjautumissivua voidaan vaatia turvakoodi, ja ylläpitäjä voi kytkeä tämän vaiheen pois.
- Pidä useita veneitä ja valitse, kuka saa avata kunkin veneen.
- Kirjoita matkapäiväkirja, jaa julkaisu ja hyväksy tai poista julkiset kommentit ennen kuin ne näytetään.
- Kirjaa moottoritunnit, huoltovälit, tarkistuslista ja matkustajat.
- Tallenna kulut kuittikuvineen, asiakirjat ja vinkit.
- Näytä anturin lähettämä lämpötila, ilmankosteus ja pilssin lukema.
- Vaihda käyttöliittymän kieli: englanti, suomi, ruotsi, venäjä tai saksa.
- Kuvat pienennetään latauksen yhteydessä (pisin sivu enintään 1600 px), jotta puhelimen kuvat eivät täytä levyä.

## Vaatimukset

- Python 3.10 tai uudempi
- pip

Tarkista:

```bash
python3 --version
```

Windowsissa voit käyttää komentoja `py --version` tai `python --version`.

## Uusi asennus

Nämä vaiheet luovat tyhjän hallintapaneelin, jossa on yksi vene ja ylläpitäjän tunnus.  
**Älä tee tätä, jos sinulla on jo tietokanta, jonka haluat säilyttää.** Käytä silloin ohjetta [Vanhan veneen siirto](#vanhan-veneen-siirto).

### 1. Hae tiedostot

```bash
git clone https://github.com/YOUR_USER/boat_dashboard.git
cd boat_dashboard
```

### 2. Luo virtuaaliympäristö ja asenna paketit

macOS ja Linux:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Windows (komentokehote):

```bat
py -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Luo ensimmäinen tietokanta

```bash
python fresh_start.py
```

Komento poistaa tässä kansiossa olevan `main.db`-tiedoston ja `boats/`-kansion ja luo sitten:

| | |
|---|---|
| Turvakoodi | `1234` |
| Käyttäjätunnus | `admin` |
| Salasana | `admin123` |
| Vene | My First Boat, liitetty käyttäjään `admin` |

Vaihda salasana ensimmäisen kirjautumisen jälkeen. Lisää oma turvakoodi kohdassa **Secure Codes** ja poista sitten `1234`.

### 4. Salli kirjautuminen omalla tietokoneella

Sovellus on tehty sivustolle, joka käyttää HTTPS-yhteyttä. Osoitteessa `http://localhost` selain ei tallenna kirjautumisevästettä, joten salasanasivu latautuu uudelleen eikä sisään pääse.

Avaa `app.py` ja muuta vain paikallista testiä varten:

```python
app.config['SESSION_COOKIE_SECURE'] = True
```

muotoon:

```python
app.config['SESSION_COOKIE_SECURE'] = False
```

Palauta arvo `True`, kun sivusto on HTTPS-yhteyden takana.

### 5. Käynnistä

```bash
python app.py
```

Avaa [http://localhost:5000](http://localhost:5000).

## Päivittäinen käyttö

1. Anna turvakoodi, jos se on käytössä.
2. Kirjaudu sisään.
3. Valitse vene. Etusivulla näkyvät moottoritunnit, anturit ja venekuvagalleria.
4. Sivuvalikosta pääset päiväkirjaan, moottorihistoriaan, huoltoon, tarkistuslistaan, matkustajiin, vinkkeihin, kuluihin, asiakirjoihin ja venetietoihin.

**Julkinen päiväkirja.** Päiväkirjan asetuksista päiväkirjan voi julkaista. Vierailijat avaavat sen osoitteesta:

```text
http://localhost:5000/<veneen-nimi>/journal
```

Välilyönnit veneen nimessä muuttuvat yhdysmerkeiksi ja nimi on pienillä kirjaimilla. Vene nimeltä `My First Boat` julkaistaan osoitteessa `/my-first-boat/journal`. Julkisen julkaisun kommentit pysyvät piilossa, kunnes avaat julkaisun kirjautuneena ja painat **Approve**.

**Turvakoodi päälle tai pois.** Kirjaudu ylläpitäjänä, avaa käyttäjävalikko ja valitse **Secure Codes**. Yläreunan kytkin laittaa lisäkoodin päälle tai pois. Pois kytkeminen ei poista koodeja.

**Lisää henkilö.** Ylläpitäjä voi luoda käyttäjiä ja liittää heidät veneeseen. Käyttäjä näkee vain veneet, joihin hänet on liitetty.

**Varmuuskopio.** Ylläpitäjän venesivulta voi ladata zip-tiedoston, jossa on yhden veneen tietokanta ja ladatut tiedostot. Säilytä myös kopio tiedostosta `main.db`. Zip ei sisällä käyttäjätilejä.

## Vanhan veneen siirto

Veneen tiedot ovat kolmessa paikassa. Veneelle, jonka tunnus on 2, tiedostot ovat:

| Kopioi tämä | Uuteen kansioon | Sisältö |
|---|---|---|
| `main.db` | `main.db` | käyttäjät, salasanat, turvakoodit, venelista |
| `boats/boat_2.db` | `boats/boat_2.db` | matkat, moottoritunnit, kulut, vinkit |
| `static/uploads/boat_2/` | `static/uploads/boat_2/` | kuvat, asiakirjat, kuitit |

Älä nimeä tiedostoa `boat_2.db` uudelleen muotoon `boat_1.db`. Numero on veneen tunnus, ja tietokannan kuvapolut käyttävät samaa numeroa.

Uudessa kansiossa:

```bash
pip install -r requirements.txt
python migrate_db.py
python app.py
```

`migrate_db.py` lisää puuttuvat taulut ja sarakkeet. Se ei poista matkoja, käyttäjiä eikä veneiden tunnuksia. Ensimmäisellä ajokerralla se kirjoittaa myös tiedostot `main.db.bak` ja `boats/boat_2.db.bak`.

**Älä** aja komentoa `fresh_start.py` kansiossa, jossa on vanha `main.db`. Se poistaa vanhat tietokannat.

Kirjaudu vanhalla käyttäjätunnuksella, salasanalla ja turvakoodilla.

## Anturilukemat

Laite voi lähettää JSONia osoitteeseen `POST /api/sensor`:

```json
{
  "boat_id": 2,
  "secret": "the-secret-set-for-this-boat",
  "temperature": 18.2,
  "humidity": 61,
  "bilge_level": 0
}
```

Aseta salaisuus ylläpitäjän venesivulla. Väärä salaisuus hylätään.

## Kansiorakenne

```text
boat_dashboard/
├── app.py              # käynnistää Flaskin
├── routes.py           # sivut ja anturirajapinta
├── models.py           # SQLite-rakenne ja päivitykset
├── auth.py             # kirjautumistarkistukset
├── config.py           # polut, salainen avain, latausrajat
├── translations.py     # englanti, suomi, ruotsi, venäjä, saksa
├── utils.py            # moottoritunnit ja kuvien pienennys
├── fresh_start.py      # tyhjä asennus (poistaa vanhat tiedot)
├── migrate_db.py       # päivitä vanha tietokanta, säilytä tiedot
├── templates/          # sivut
├── static/             # kuvakkeet ja ajonaikaiset lataukset
├── boats/              # boat_1.db, boat_2.db, … (ei gitiin)
└── main.db             # käyttäjät ja venelista (ei gitiin)
```

## Asetukset

`config.py` lukee nämä asetukset:

| Asetus | Merkitys |
|---|---|
| `SECRET_KEY` | Aseta tämä ympäristömuuttuja palvelimella. Älä jätä oletusavainta julkiselle sivustolle. |
| `TIMEZONE` | Päiväkirjojen "nyt". Oletus `Europe/Helsinki`. |
| `ALLOWED_EXTENSIONS` | png, jpg, jpeg, gif, webp, pdf, gpx |
| `MAX_CONTENT_LENGTH` | 25 Mt latausta kohti, asetettu myös tiedostossa `app.py` |

Luodut tiedostot on listattu tiedostossa `.gitignore`: `*.db`, `boats/`, `static/uploads/`, `logs/` ja virtuaaliympäristöt. Älä vie niitä versionhallintaan. Niissä on salasanoja, yksityisiä matkoja ja kuvia.

## Tuotantokäyttö

- Käytä HTTPS-yhteyttä ja jätä `SESSION_COOKIE_SECURE = True`.
- Vaihda ylläpitäjän salasana ja turvakoodi.
- Aseta pitkä satunnainen `SECRET_KEY`.
- `python app.py` käyttää Flaskin kehityspalvelinta (`debug=True`). Julkisella palvelimella aja sovellus WSGI-palvelimella, esimerkiksi gunicornilla, nginxin tai Caddyn takana.
- Kehityspalvelin kuuntelee kaikkia verkkoliitäntöjä portissa 5000.

## Lisenssi

MIT
