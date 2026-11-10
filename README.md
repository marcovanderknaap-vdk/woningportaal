# Zeeuws Woningaanbod – conceptapplicatie

Een woningportaal met het koopaanbod van aangesloten Zeeuwse makelaars.
Elke dag haalt de applicatie het aanbod op van de websites van de makelaars,
slaat de hoofdfoto, vraagprijs en objectdetails lokaal op en werkt de status bij.

## Wat zit erin

| Onderdeel | Waar |
|---|---|
| Backend (makelaars beheren, woningen inzien/verbergen, logboek) | `/beheer/` (Django-beheer) |
| Publieke site met filters (woonplaats, prijsklasse, soort woning) | `/` |
| Detailpagina per woning met link naar de makelaar | `/woning/<id>/` |
| Overzicht aangesloten makelaars | `/makelaars/` |
| Dagelijkse controle | `python manage.py ophalen` |
| Statische export (GitHub Pages) | `python manage.py export_statisch` |

### Statussen
Beschikbaar · Onder optie (ook “onder bod”) · Verkocht onder voorbehoud · Verkocht.
Verkochte woningen blijven 30 dagen zichtbaar (`VERKOCHT_ZICHTBAAR_DAGEN`).

### Label “nieuw”
Een woning die korter dan 14 dagen in de database staat, krijgt het label *nieuw*.
Uitzondering: woningen die bij de **allereerste** controle van een makelaar worden
gevonden, krijgen het label niet. Anders zou bij een nieuwe makelaar ineens het
hele bestaande aanbod als “nieuw” verschijnen.

## Hoe het ophalen werkt

1. **Woninglinks vinden.** Per makelaar op één van twee manieren:
   * *Aanbodpagina*: de overzichtspagina en alle vervolgpagina's (`/page/2/`, `pagina-2`, `?page=2`) worden doorlopen;
   * *Sitemap*: een XML-sitemap met alle woningen (nodig bij sites die het aanbod met JavaScript laden, zoals Kuub).

   Welke links woningen zijn, wordt automatisch bepaald. Lukt dat niet goed, vul dan in de
   backend onder *Geavanceerd* een **patroon voor woninglinks** in.
2. **Nieuwe woningen** worden gelezen via één generieke lezer. Die herkent label/waarde-paren
   ("Vraagprijs", "Status", "Woonoppervlakte", …) en de hoofdfoto (`og:image`).
   **Alle** gevonden kenmerken worden bewaard in het veld *kenmerken*, zodat extra
   objectdetails later zonder nieuwe import zichtbaar gemaakt kunnen worden.
   Huurwoningen, garages en bedrijfsruimtes, en woningen die al verkocht zijn, worden overgeslagen.
3. **Bekende woningen** worden elke dag opnieuw bekeken: status- en prijswijzigingen worden
   bijgewerkt en in een historie bewaard. Een pagina die verdwijnt, gaat naar *offline* en
   wordt niet meer getoond.
4. **Beleefd crawlen**: `robots.txt` wordt gerespecteerd, inclusief de `Crawl-delay`
   (Casco vraagt 30 s, Kuub 10 s). Daarom duurt een volledige controle ongeveer een uur.
5. **Storing?** Een makelaar waarbij geen enkele link gevonden wordt, of waarbij te veel pagina's
   niet te lezen zijn, krijgt de toestand “⚠ probleem”. Er gaat dan een e-mail naar `RAPPORT_EMAIL`.

### Nieuwe makelaar toevoegen
1. Backend → Makelaars → *Makelaar toevoegen*. Vul bedrijfsgegevens en de **URL naar het aanbod** in.
2. Selecteer de makelaar in de lijst en kies de actie **“Testen”**. Na een paar minuten staat
   onder *Controles (logboek)* hoeveel woninglinks er gevonden zijn en hoe de eerste 3 woningen gelezen werden.
3. Klopt het? Dan neemt de dagelijkse controle de makelaar mee.

## Lokaal draaien

```bash
pip install -r requirements.txt
python manage.py migrate
python manage.py makelaars_laden        # de makelaars uit makelaars.json
python manage.py createsuperuser        # inlog voor de backend
python manage.py ophalen                # eerste import (± 1 uur)
python manage.py runserver              # http://127.0.0.1:8000/ en /beheer/
```

## Testen via GitHub (zonder eigen hosting)

* **De dagelijkse controle** draait als GitHub Actions-workflow (`.github/workflows/dagelijks.yml`).
  Database en foto's worden bewaard in de branch `data`.
* **Alleen de site bijwerken** (zonder het aanbod opnieuw op te halen): *Actions → Dagelijkse controle →
  Run workflow*, vink **"Alleen de site bijwerken"** aan. Dit gebeurt ook automatisch na elke codewijziging
  op `main` en duurt een paar minuten.
* **De publieke site** wordt na elke controle gepubliceerd op GitHub Pages:
  `https://<gebruiker>.github.io/<repository>/`.
  Zet dit eenmalig aan: *Settings → Pages → Source: GitHub Actions*.
* **De backend** heeft een draaiende server nodig, en die biedt GitHub Pages niet. Voor de testfase:
  * open de repository in **GitHub Codespaces** (*Code → Codespaces → Create*). De backend start
    dan vanzelf op `/beheer/`. Na het wijzigen van makelaars: `bash scripts/beheer.sh bewaren`;
  * of wijzig `makelaars.json` direct op github.com. De workflow leest dat bestand elke dag in.
* **E-mail bij storing:** GitHub mailt de eigenaar automatisch als de workflow faalt. Een eigen
  storingsrapport kan via deze *repository secrets* (Settings → Secrets and variables → Actions):
  `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_FROM`, `RAPPORT_EMAIL`.

## Naar productie
Voor de echte site is een kleine server (VPS, ± €5–10 per maand) het eenvoudigst. Daarop draaien
de website, de backend en de dagelijkse taak (`cron`: `python manage.py ophalen`). Stel daarbij in:
`DJANGO_DEBUG=false`, `DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS` en de e-mailinstellingen.
SQLite volstaat voor duizenden woningen; PostgreSQL kan later.

## Database: SQLite of PostgreSQL
Zonder instelling gebruikt de applicatie SQLite (één bestand; zo werkt de GitHub-testomgeving).
Op de server wordt PostgreSQL gebruikt door `DATABASE_URL` te zetten:

```bash
DATABASE_URL=postgres://gebruiker:wachtwoord@localhost:5432/portaal
```

De bestaande gegevens overzetten van SQLite naar PostgreSQL (getest met de echte database):

```bash
# 1. exporteren uit SQLite (zonder DATABASE_URL)
python manage.py dumpdata --natural-foreign --natural-primary --exclude contenttypes \
  --exclude auth.permission --exclude sessions --exclude admin.logentry -o export.json
# 2. inlezen in PostgreSQL
export DATABASE_URL=postgres://...
python manage.py migrate
python manage.py loaddata export.json
```
Kopieer daarnaast de map met foto's en logo's (`data/media`). Bij elke codewijziging draaien de tests
op GitHub automatisch op zowel SQLite als PostgreSQL (`.github/workflows/tests.yml`).

## Instellingen (omgevingsvariabelen)
`PORTAAL_NAAM`, `NIEUW_DAGEN` (14), `VERKOCHT_ZICHTBAAR_DAGEN` (30), `VERKOCHT_CONTROLE_DAGEN` (30),
`SCRAPER_MIN_DELAY` (2 s), `FOTO_MAX_BREEDTE` (1200 px), `RAPPORT_EMAIL`, `EMAIL_*`,
`PORTAAL_INDEXEREN` (uit: elke pagina krijgt `noindex` en robots.txt blokkeert alles; zet op `true` bij de livegang).
