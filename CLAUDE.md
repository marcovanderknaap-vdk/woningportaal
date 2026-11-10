# Weune – huisstijl en projectcontext

Huisstijl en projectcontext van Weune. Claude Code leest dit bestand bij elke sessie en houdt zich aan deze huisstijl. Lettertypes worden zelf gehost vanuit `aanbod/static/fonts/`; de design tokens staan in `aanbod/static/brand/weune-tokens_20261110.css`.

## Over Weune

- Weune is het Zeeuwse woningportaal: één plek voor het woningaanbod in Zeeland, vergelijkbaar met Funda maar regionaal.
- "Weune" is Zeeuws voor "wonen". Schrijf de naam als Weune in lopende tekst; het logo zelf is in kleine letters (weune).
- Domein: www.weune.nl.
- Alleen NVM-makelaars kunnen aanbod plaatsen. Benoem dit waar het vertrouwen geeft (footer, over-ons, makelaarspagina's), maar gebruik nooit het NVM-logo of NVM-beeldmerk zonder schriftelijke toestemming van de NVM.
- Doelgroep: woningzoekers in en naar Zeeland (Zeeuwse eilanden en Zeeuws-Vlaanderen, ook Belgische kopers) en de aangesloten NVM-makelaars.
- Pay-off: **"Wonen in Zeeland. Hier wil ik weune!"** – altijd letterlijk zo, met "weune" in kleine letters (woordgrap op het Zeeuwse woord). Dit is de enige kop met een uitroepteken. Staat in de hero van de homepage, de paginatitel en de footer.
- Taal: Nederlands. Spreek bezoekers aan met "je/jouw". Toon: helder, warm, nuchter Zeeuws. Geen marketingjargon, geen uitroeptekens in koppen.

## Logo

Het logo bestaat uit een beeldmerk (afgeronde tegel met een dak boven een golf) en een woordmerk (weune, getekend als ronde lijnletters in dezelfde lijndikte als het dak). Het woordmerk is geen lettertype: gebruik altijd de SVG-bestanden, nooit "weune" in Outfit of een ander font als vervanging.

Bestanden in `aanbod/static/brand/`:

| Bestand | Gebruik |
|---|---|
| `weune-logo-horizontaal-blauw_20261110.svg` | Standaard: header op witte of lichte achtergrond |
| `weune-logo-horizontaal-wit_20261110.svg` | Op nacht (#0B1C3F) of blauw: footer, hero met donkere overlay |
| `weune-logo-horizontaal-nacht_20261110.svg` | Eenkleurig donker, bijvoorbeeld drukwerk of documenten |
| `weune-logo-gestapeld-*_20261110.svg` | Vierkante ruimtes: social, inlogscherm, app-splash |
| `weune-beeldmerk-*_20261110.svg` | Alleen als het woordmerk al in beeld is of bij weinig ruimte (mobiele header kleiner dan 360px, kaartpins) |
| `weune-woordmerk-*_20261110.svg` | Alleen tekst, bijvoorbeeld in een e-mailhandtekening naast het M2- of makelaarslogo |

Regels:
- Vrije ruimte rondom het logo: minimaal de hoogte van de golf (ongeveer 1/5 van de tegelhoogte).
- Minimale grootte horizontaal logo: 120px breed op scherm. Daaronder het beeldmerk gebruiken.
- Header: horizontaal logo op 32–40px hoogte, links uitgelijnd, linkt naar `/`.
- Niet doen: het logo vervormen, roteren, andere kleuren geven, schaduwen of verlopen toevoegen, of het logo op een drukke foto zetten zonder donkere overlay.
- `alt="Weune"` op het logo; als het logo de homelink is: `aria-label="Weune – naar de homepage"`.

Website-iconen (vaste bestandsnamen, in `aanbod/static/website/`, op de site geserveerd vanaf de hoofdmap): `favicon.ico`, `favicon.svg`, `apple-touch-icon.png`, `icon-192.png`, `icon-512.png`, `og-image.png` (1200×630).

```html
<link rel="icon" href="/favicon.ico" sizes="any">
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<link rel="apple-touch-icon" href="/apple-touch-icon.png">
<meta name="theme-color" content="#0A3A86">
<meta property="og:image" content="https://www.weune.nl/og-image.png">
```

## Kleuren

Alle kleuren staan als CSS-variabelen in `weune-tokens_20261110.css` (en als JSON in `weune-tokens_20261110.json`). Gebruik altijd de variabelen, nooit losse hexcodes in componenten.

| Token | Hex | Gebruik |
|---|---|---|
| `--weune-blauw` | #0A3A86 | Primair: logo, primaire knoppen, actieve tabs en filters |
| `--weune-blauw-hover` | #082E6B | Hover/active van primaire knoppen |
| `--weune-nacht` | #0B1C3F | Koppen, footer, donkere vlakken, overlay op foto's |
| `--weune-golf` | #8DBBF2 | Decoratief accent op blauw of nacht (golflijnen, iconen). Nooit als tekst op wit |
| `--weune-golf-licht` | #E3EEFC | Lichte vlakken, geselecteerde filterchips, hover van secundaire knop |
| `--weune-link` | #1F5BB5 | Tekstlinks op wit |
| `--weune-zand` | #F2C14E | Labels "Nieuw" en "Open huis", altijd met nacht-tekst |
| `--weune-oppervlak` | #F5F8FD | Paginagrond achter kaarten, zijbalken |
| `--weune-lijn` | #D9E1EE | Randen en scheidingslijnen |
| `--weune-tekst` | #1A2333 | Lopende tekst |
| `--weune-tekst-2` | #4A5872 | Subtekst, woningkenmerken |
| `--weune-tekst-3` | #66728A | Metadata en placeholders, minimaal 14px |
| `--weune-tekst-op-donker` | #C9D6EE | Subtekst op nacht |
| `--weune-beschikbaar` | #1E7A4C | Status "Beschikbaar" |
| `--weune-onder-bod` | #B45309 | Status "Onder bod" en "Verkocht onder voorbehoud" |
| `--weune-verkocht` | #B42318 | Status "Verkocht" |

Verhouding: vooral wit en oppervlak, blauw voor interactie, nacht voor koppen en de footer, zand spaarzaam (alleen labels). Alle tekstcombinaties hierboven halen WCAG AA (minimaal 4,5:1); houd dat zo bij nieuwe combinaties.

Het blauw is afgestemd op de NVM-kleurstelling maar is de eigen Weune-kleur. Als de exacte NVM-hexcode wordt aangeleverd, alleen `--weune-blauw` en `--weune-blauw-hover` aanpassen en het contrast opnieuw controleren.

## Typografie

- Koppen, prijzen en grote cijfers: **Outfit** 600 (700 alleen voor de hero-kop, 500 voor kleine tussenkoppen).
- Lopende tekst, formulieren, kenmerken en tabellen: **Inter** 400, nadruk 500/600.
- Beide via Google Fonts (vrije licentie), met `display=swap`. Zelf hosten mag ook (bijv. via `@fontsource/outfit` en `@fontsource/inter`), dat is beter voor privacy (AVG) en snelheid.
- Schaal: display 40–56px, h1 32–40px, h2 28px, h3 22px, h4 18px, tekst 16px, klein 14px, labels 12px in hoofdletters. Vraagprijs op een woningkaart 24px Outfit 600.
- Regelhoogte koppen 1.15, tekst 1.6. Maximale regellengte lopende tekst: ongeveer 70 tekens.
- Prijzen altijd met `font-variant-numeric: tabular-nums` en in het formaat `€ 349.000 k.k.` (spatie na het euroteken, punt als duizendtalscheiding).
- Oppervlaktes als `124 m²`, inhoud als `410 m³`, perceel als `312 m²`.

## Vorm en componenten

- Afrondingen: 8px (velden, labels), 12px (knoppen), 16px (woningkaarten, panelen), 24px (hero-zoekbalk, grote beelden). De afgeronde tegel van het beeldmerk is het uitgangspunt: vriendelijk, niet bol.
- Ruimteschaal: 4, 8, 12, 16, 24, 32, 48, 64, 96px. Maximale contentbreedte 1280px.
- Schaduwen zacht en blauwgetint (`--weune-schaduw-kaart`, `--weune-schaduw-hover`), geen harde zwarte schaduwen.
- Knoppen minimaal 44px hoog. Primair: blauw met witte tekst. Secundair: wit met blauwe rand en tekst.
- Focus altijd zichtbaar via `--weune-focus`.
- Woningkaart: foto 4:3 met 16px afronding bovenaan, statuslabel linksboven op de foto, daaronder adres (h4, nacht), plaats (tekst-2), vraagprijs (prijs-stijl) en een regel kenmerken met iconen (woonoppervlak, perceel, slaapkamers, energielabel).
- Iconen: lijniconen met afgeronde uiteinden, 1,75–2px lijndikte, zoals Lucide. Geen emoji.
- Het golfmotief uit het logo mag als subtiel decoratief element terugkomen (bijv. een golflijn in `--weune-golf` boven de footer). Niet overdadig gebruiken.

## Beeld

- Foto's van woningen en Zeeuwse omgeving: daglicht, natuurlijke kleuren, geen zware filters.
- Tekst op een foto alleen met een overlay van nacht op 50–70% dekking.

## Techniek en kwaliteit

- Mobiel eerst: het merendeel van de woningzoekers zoekt op de telefoon. Alles moet werken vanaf 360px breed.
- Toegankelijkheid: WCAG 2.1 AA, echte `<button>`- en `<a>`-elementen, labels bij formuliervelden, alt-tekst bij woningfoto's (bijv. "Woonkamer met openslaande deuren naar de tuin").
- Bestandsnamen van huisstijlbestanden en exports eindigen op een datumstempel `_JJJJMMDD`, zodat versies uit elkaar te houden zijn. Uitzondering: bestanden waarvan browsers de naam vastleggen (favicon.ico, apple-touch-icon.png e.d.).
