# Weune – het Zeeuwse woningportaal

Een woningportaal met het koopaanbod van aangesloten Zeeuwse makelaars.
Elke dag haalt de applicatie het aanbod op van de websites van de makelaars,
slaat de hoofdfoto, vraagprijs en objectdetails lokaal op en werkt de status bij.

De huisstijl (logo's, kleuren, lettertypes) staat in `CLAUDE.md` en `aanbod/static/brand/`.

## Wat zit erin

| Onderdeel | Waar |
|---|---|
| Backend (makelaars beheren, woningen inzien/verbergen, logboek) | `/beheer/` (Django-beheer) |
| Publieke site met filters (woonplaats, prijsklasse, soort woning) | `/` |
| Detailpagina per woning met link naar de makelaar | `/woning/<id>/` |
| Overzicht aangesloten makelaars | `/makelaars/` |
| Zoeken op kaart (schakelaar Lijst / Kaart, of `/?weergave=kaart`) | coördinaten via PDOK Locatieserver, kaart: OpenStreetMap-tegels (ook België) + Leaflet (zelf gehost); tegeldienst instelbaar via `KAART_TEGELS_URL` |
| Kaartlocaties aanvullen | `python manage.py geocoderen` (gebeurt ook automatisch bij elke run) |
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

## Opruimen (opslag beperken)
Dagelijks (`python manage.py opruimen`, ook in de workflow):

| Termijn | Wat gebeurt er | Instelling |
|---|---|---|
| 30 dagen na verkoop / verdwijnen | niet meer zichtbaar op de site | `VERKOCHT_ZICHTBAAR_DAGEN` |
| 90 dagen | foto verwijderd; woning blijft als archiefregel (adres, prijzen, historie) | `FOTO_BEWAREN_DAGEN` |
| 2 jaar | archiefregel verwijderd | `ARCHIEF_BEWAREN_DAGEN` |
| 90 dagen | logboeken van controles verwijderd | `LOGBOEK_BEWAREN_DAGEN` |
| 1 jaar | genegeerde links verwijderd | `GENEGEERD_BEWAREN_DAGEN` |

Losse fotobestanden zonder woning worden ook opgeruimd, met een veiligheidsrem: nooit als het om meer dan
10% van alle bestanden gaat. De branch `data` op GitHub bewaart alleen de laatste stand (geen geschiedenis).

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
`PORTAAL_NAAM` (Weune), `PORTAAL_SITE_URL` (https://www.weune.nl), `NIEUW_DAGEN` (14), `VERKOCHT_ZICHTBAAR_DAGEN` (30), `VERKOCHT_CONTROLE_DAGEN` (30),
`SCRAPER_MIN_DELAY` (2 s), `FOTO_MAX_BREEDTE` (1200 px), `RAPPORT_EMAIL`, `EMAIL_*`,
`KAART_TEGELS_URL` en `KAART_ATTRIBUTIE` (achtergrondkaart; zie hieronder), `PORTAAL_INDEXEREN` (uit: elke pagina krijgt `noindex` en robots.txt blokkeert alles; zet op `true` bij de livegang).

### Achtergrondkaart bij de livegang
De testomgeving gebruikt de openbare kaarttegels van OpenStreetMap. Die zijn bedoeld voor beperkt gebruik.
Zet voor de publieke site met veel bezoekers een eigen tegeldienst in, bijvoorbeeld MapTiler (EU, gratis
instapniveau) of zelf gehoste tegels, via `KAART_TEGELS_URL` en `KAART_ATTRIBUTIE`. Er hoeft dan niets
aan de code te veranderen.

### Bezoekers meten bij de makelaars
Alle links naar makelaarssites krijgen UTM-parameters (`utm_source=weune`, `utm_medium=referral`,
`utm_campaign=woningaanbod`, `utm_content=woningpagina|omschrijving|makelaarsoverzicht`). Makelaars zien zo
in Google Analytics of een vergelijkbaar pakket hoeveel bezoekers Weune oplevert. Zie de templatefilter `via_weune`.

## Planning: bij de verhuizing naar de eigen server
Afgesproken tijdens de testfase (november 2026). Tot de verhuizing draait de controle één keer per dag op GitHub.

- [ ] **Server:** Hetzner Cloud CPX12 (of CPX22 voor meer ruimte), met automatische updates en dagelijkse back-ups.
- [ ] **Test- en productieomgeving** op dezelfde server: branch `ontwikkeling` → `test.weune.nl` (met wachtwoord), branch `main` → `www.weune.nl`.
- [ ] **PostgreSQL** in plaats van SQLite (de code is er al op voorbereid en getest; zie "Database: SQLite of PostgreSQL").
- [ ] **Controle in twee snelheden:**
  - elk uur een snelle ronde: alleen overzichtspagina's/sitemaps bekijken en nieuwe woningen ophalen;
  - één keer per dag (eventueel 2–3×) een volledige ronde: alle bekende woningen op status en prijs controleren.
- [ ] **Makelaars parallel controleren**, met per site de gevraagde wachttijd (nodig bij ±40 makelaars).
- [ ] **Storingsmails slimmer:** alleen bij een nieuwe storing en bij herstel, plus één dagelijkse samenvatting.
- [ ] **Eigen kaarttegeldienst** (bijv. MapTiler) via `KAART_TEGELS_URL`, in plaats van de openbare OpenStreetMap-tegels.
- [ ] **Indexeren aanzetten** voor de publieke site (`PORTAAL_INDEXEREN=true`), niet voor de testomgeving.
- [ ] **E-maildienst** (bijv. Brevo of Mailgun EU) voor storingsmails en later de zoekprofielen.

Daarna, afhankelijk van de uitkomst van het makelaarsoverleg (november 2026):

- [ ] **Zoekprofielen met e-mailmeldingen:** inschrijven met bevestigingsmail, afmeldlink in elke mail,
  privacyverklaring; profiteert van de snelle ronde per uur.
- [ ] **Meerdere foto's, plattegronden en volledige tekst, per makelaar met toestemming:**
  - instelling per makelaar in de backend: "één foto + ingekorte tekst" of "tot 8 foto's + plattegronden +
    volledige tekst" (standaard), inclusief vastlegging wanneer en door wie toestemming is gegeven;
  - toestemming ingetrokken → extra foto's en volledige tekst direct verwijderen;
  - alleen op de eigen server (± 1–1,5 MB per woning, 4–6 GB bij 40 makelaars; CPX22 aanbevolen),
    foto's als WebP in twee formaten (miniatuur en groot), lazy loading en een fotogalerij;
  - foto's ophalen per site testen (Realworks-sites eerst; galerijen via JavaScript vragen maatwerk),
    gewijzigde of verwijderde foto's bijhouden;
  - volledige tekst met alinea's en opsommingen bewaren; keuze maken over `canonical` (dubbele inhoud);
  - deelnamevoorwaarden: makelaar verklaart de foto's (ook van fotografen) aan Weune te mogen doorgeven.

Nog aan te leveren: contactadres voor de pagina "Over Weune" (bijv. voor makelaars die willen aansluiten).
