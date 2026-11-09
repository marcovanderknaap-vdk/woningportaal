"""Generieke lezer voor woningdetailpagina's.

Vrijwel alle makelaarssites (Realworks, WordPress-koppelingen, eigen sites)
tonen de kenmerken als label/waarde-paren ('Vraagprijs' → '€ 395.000,- k.k.')
en de hoofdfoto als Open Graph-afbeelding. Deze module leest die uit en
vertaalt ze naar vaste velden. Alle gevonden paren worden daarnaast bewaard,
zodat later extra objectdetails toegevoegd kunnen worden zonder opnieuw te
hoeven ophalen.
"""
import json
import re
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup

from .plaatsen import zoek_plaats

# Label op de site (kleine letters, zonder ':') -> intern veld
LABELS = {
    "vraagprijs": "prijs", "koopsom": "prijs", "koopprijs": "prijs", "prijs": "prijs",
    "koopsom vanaf": "prijs", "vanaf": "prijs",
    "huurprijs": "huurprijs", "huur": "huurprijs",
    "status": "status", "beschikbaarheid": "status",
    "woonoppervlakte": "woonoppervlakte", "gebruiksoppervlakte wonen": "woonoppervlakte",
    "woonoppervlak": "woonoppervlakte", "woonopp.": "woonoppervlakte", "woonopp": "woonoppervlakte",
    "wonen": "woonoppervlakte",
    "perceeloppervlakte": "perceel", "perceeloppervlak": "perceel", "perceelopp.": "perceel",
    "perceel": "perceel",
    "inhoud": "inhoud",
    "aantal kamers": "kamers", "kamers": "kamers",
    "aantal slaapkamers": "slaapkamers", "slaapkamers": "slaapkamers",
    "bouwjaar": "bouwjaar", "bouwperiode": "bouwjaar",
    "energielabel": "energielabel", "energieklasse": "energielabel",
    "soort woning": "soort", "soort object": "soort_object", "soort appartement": "soort",
    "soort woonhuis": "soort", "soortobject": "soort_object",
    "type woning": "type", "type": "type", "type object": "soort_object",
    "aangeboden sinds": "aangeboden_sinds", "aanvaarding": "aanvaarding",
    "bouwvorm": "bouwvorm", "soort bouw": "bouwvorm", "ligging": "ligging",
    "tuin": "tuin", "garage": "garage", "isolatie": "isolatie", "verwarming": "verwarming",
    "aantal woonlagen": "woonlagen", "aantal badkamers": "badkamers",
    "externe bergruimte": "externe_bergruimte", "overige inpandige ruimte": "overige_inpandige_ruimte",
}

STATUS_PATRONEN = [
    ("verkocht_ov", re.compile(r"verkocht\s+o(nder)?\.?\s*v(oorbehoud)?\.?|verkocht\s+ovb", re.I)),
    ("onder_optie", re.compile(r"onder\s+(optie|bod)|in\s+optie|optie\b", re.I)),
    ("verkocht", re.compile(r"\bverkocht\b", re.I)),
    ("verhuurd", re.compile(r"\bverhuurd\b", re.I)),
    ("ingetrokken", re.compile(r"ingetrokken|niet\s+meer\s+beschikbaar", re.I)),
    ("beschikbaar", re.compile(r"beschikbaar|te\s+koop|in\s+verkoop|nieuw\s+in\s+verkoop|nieuw\b|prijs\s+verlaagd", re.I)),
]

GEEN_WONING = re.compile(
    r"garage(box)?\b|parkeer|bedrijfs|kantoor|winkel|horeca|ligplaats|berging\b|stalling|belegging", re.I
)


@dataclass
class Resultaat:
    url: str
    adres: str = ""
    postcode: str = ""
    woonplaats: str = ""
    vraagprijs: int | None = None
    prijs_tekst: str = ""
    prijs_conditie: str = ""
    status: str | None = None  # None = niet gevonden
    status_tekst: str = ""
    woningtype: str = "overig"
    woonoppervlakte: int | None = None
    perceeloppervlakte: int | None = None
    inhoud: int | None = None
    kamers: int | None = None
    slaapkamers: int | None = None
    bouwjaar: int | None = None
    energielabel: str = ""
    omschrijving: str = ""
    foto_url: str = ""
    kenmerken: dict = field(default_factory=dict)
    is_huur: bool = False
    geen_woning: bool = False

    @property
    def bruikbaar(self):
        """Genoeg gevonden om als woning op te nemen?"""
        return bool(self.adres or self.woonplaats) and (self.vraagprijs is not None or self.status is not None)


# -- hulpfuncties ----------------------------------------------------------

def _getal(tekst):
    if not tekst:
        return None
    m = re.search(r"\d[\d.]*", tekst.replace("\xa0", " "))
    if not m:
        return None
    try:
        return int(m.group(0).replace(".", ""))
    except ValueError:
        return None


def parse_prijs(tekst):
    if not tekst:
        return None, ""
    t = tekst.replace("\xa0", " ")
    m = re.search(r"€\s*([\d.]+)", t) or re.search(r"([\d]{1,3}(?:\.\d{3})+)", t)
    prijs = int(m.group(1).replace(".", "")) if m else None
    conditie = ""
    if re.search(r"k\.?\s?k\.?|kosten koper", t, re.I):
        conditie = "k.k."
    elif re.search(r"v\.?\s?o\.?\s?n\.?|vrij op naam", t, re.I):
        conditie = "v.o.n."
    return prijs, conditie


def normaliseer_status(tekst):
    if not tekst:
        return None
    for code, patroon in STATUS_PATRONEN:
        if patroon.search(tekst):
            return code
    return None


def normaliseer_type(*teksten):
    t = " ".join(x for x in teksten if x).lower()
    if not t:
        return "overig"
    if re.search(r"bouwgrond|bouwkavel|\bkavel", t):
        return "bouwgrond"
    if re.search(r"appartement|bovenwoning|benedenwoning|maisonnette|penthouse|portiek|galerij|flat\b|studio|bovenhuis|benedenhuis", t):
        return "appartement"
    if re.search(r"2[\s-]?onder[\s-]?1[\s-]?kap|twee[\s-]?onder[\s-]?een[\s-]?kap|halfvrijstaand|half vrijstaand|geschakelde 2", t):
        return "2-onder-1-kap"
    if re.search(r"hoekwoning|eindwoning|hoekhuis", t):
        return "hoekwoning"
    if re.search(r"tussenwoning|rijwoning|tussenhuis|rijtjeshuis", t):
        return "tussenwoning"
    if re.search(r"vrijstaand|villa|landhuis|bungalow|woonboerderij|boerderij", t):
        return "vrijstaand"
    if re.search(r"geschakeld", t):
        return "2-onder-1-kap"
    return "overig"


TYPE_WOORDEN = {
    "vrijstaand": r"vrijstaande (woning|villa|boerderij|woonboerderij)|\bvilla\b|landhuis|bungalow|woonboerderij",
    "2-onder-1-kap": r"2[\s-]?onder[\s-]?1[\s-]?kap|twee[\s-]?onder[\s-]?een[\s-]?kap|halfvrijstaand",
    "hoekwoning": r"hoekwoning|eindwoning",
    "tussenwoning": r"tussenwoning|rijwoning",
    "appartement": r"\bappartement\b|bovenwoning|benedenwoning|penthouse|maisonnette",
    "bouwgrond": r"bouwgrond|bouwkavel",
}


def type_uit_tekst(tekst):
    tekst = tekst.lower()
    telling = {t: len(re.findall(p, tekst)) for t, p in TYPE_WOORDEN.items()}
    beste = max(telling, key=telling.get)
    if telling[beste] == 0 or list(telling.values()).count(telling[beste]) > 1:
        return "overig"
    return beste


def _schoon(s):
    return re.sub(r"\s+", " ", s.replace("\xa0", " ")).strip()


def _tekstlijst(soup):
    """Alle tekstfragmenten van de pagina in volgorde, met m²/m³-reparatie."""
    fragmenten = [_schoon(s) for s in soup.stripped_strings]
    fragmenten = [f for f in fragmenten if f]
    samengevoegd = []
    for f in fragmenten:
        if f in ("2", "3") and samengevoegd and re.search(r"\bm$", samengevoegd[-1]):
            samengevoegd[-1] += "²" if f == "2" else "³"
        else:
            samengevoegd.append(f)
    return samengevoegd


def _label_paren(soup):
    """Zoek label/waarde-paren: eerst in <dl> en tabellen, daarna in de tekststroom."""
    paren = {}

    def voeg_toe(label, waarde):
        label = _schoon(label).rstrip(":").strip()
        waarde = re.sub(r"(\d)\s*m\s?([23])\b", lambda m: m.group(1) + " m" + ("²" if m.group(2) == "2" else "³"), _schoon(waarde))
        if not label or not waarde or len(label) > 60 or len(waarde) > 300:
            return
        sleutel = label.lower()
        if waarde.lower() == sleutel:
            return
        paren.setdefault(sleutel, (label, waarde))

    for dl in soup.find_all("dl"):
        for dt in dl.find_all("dt"):
            dd = dt.find_next_sibling("dd")
            if dd:
                voeg_toe(dt.get_text(" "), dd.get_text(" "))
    for tr in soup.find_all("tr"):
        cellen = tr.find_all(["th", "td"], recursive=False)
        if len(cellen) == 2:
            voeg_toe(cellen[0].get_text(" "), cellen[1].get_text(" "))

    fragmenten = _tekstlijst(soup)
    for i, f in enumerate(fragmenten[:-1]):
        sleutel = f.rstrip(":").strip().lower()
        if sleutel in LABELS:
            waarde = fragmenten[i + 1]
            # 'Energielabel | Energielabel | E' → sla dubbele label over
            if waarde.rstrip(":").strip().lower() == sleutel and i + 2 < len(fragmenten):
                waarde = fragmenten[i + 2]
            if waarde.rstrip(":").strip().lower() in LABELS:
                continue  # label zonder waarde
            voeg_toe(f, waarde)
        else:
            # Label en waarde in één fragment: 'Vraagprijs € 1.425.000 k.k.' of 'Bouwjaar: 1976'
            m = INLINE_LABEL.match(f)
            if m and m.group(1).lower() in LABELS:
                voeg_toe(m.group(1), m.group(2))
    return paren


INLINE_LABEL = re.compile(
    r"^(" + "|".join(sorted((re.escape(l) for l in LABELS), key=len, reverse=True)) + r")\s*:?\s+([€\d].{0,80})$",
    re.I,
)


def _json_ld(soup):
    blokken = []
    for s in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(s.string or s.get_text() or "")
        except (ValueError, TypeError):
            continue
        stapel = [data]
        while stapel:
            d = stapel.pop()
            if isinstance(d, list):
                stapel.extend(d)
            elif isinstance(d, dict):
                blokken.append(d)
                stapel.extend(v for v in d.values() if isinstance(v, (dict, list)))
    return blokken


def _meta(soup, prop):
    tag = soup.find("meta", attrs={"property": prop}) or soup.find("meta", attrs={"name": prop})
    return _schoon(tag["content"]) if tag and tag.get("content") else ""


TITEL_PREFIX = re.compile(
    r"^.*?\b(te koop|te huur|verkocht(?: onder voorbehoud)?|onder (?:bod|optie))\s*[:\-–]\s*", re.I
)
POSTCODE = re.compile(r"\b(\d{4})\s?([A-Z]{2})\b")
STRAAT_NUMMER = re.compile(r"^(?P<straat>.+?\s\d+(?:\s?[-/]?\s?[A-Za-z0-9]{1,4}\b)?)")


def parse_adres(titel, url):
    """Haal adres, postcode en woonplaats uit een paginatitel (met URL als reserve)."""
    t = _schoon(titel)
    t = TITEL_PREFIX.sub("", t)
    t = re.split(r"\s[|–—]\s|\s-\s(?=[A-Z])", t)[0]
    t = re.split(r":\s", t)[0]
    t = re.sub(r"^(appartement|woonhuis|woning|huis|bovenwoning|benedenwoning|villa|bouwgrond|bouwkavel)\s+", "", t, flags=re.I)
    postcode = ""
    m = POSTCODE.search(t)
    if m:
        postcode = f"{m.group(1)} {m.group(2)}"
    plaats = zoek_plaats(t) or zoek_plaats(urlsplit(url).path.replace("/", " "))
    adres = ""
    m = STRAAT_NUMMER.search(t)
    if m:
        adres = m.group("straat").strip(" ,(")
        # Plaatsnaam of 'in' die achter het nummer is meegekomen weghalen
        adres = re.sub(r"\s+(in|te)$", "", adres, flags=re.I)
        if plaats and adres.lower().endswith(" " + plaats.lower()):
            adres = adres[: -len(plaats) - 1]
    if not plaats and m:
        rest = t[m.end():]
        rest = POSTCODE.sub("", rest)
        rest = re.sub(r"^[\s,(]*(in|te)?\s*", "", rest, flags=re.I)
        kandidaat = re.split(r"[,()|]", rest)[0].strip()
        if kandidaat and len(kandidaat) <= 40 and not re.search(r"\d", kandidaat):
            plaats = kandidaat.title() if kandidaat.isupper() or kandidaat.islower() else kandidaat
    return adres, postcode, plaats or ""


def _status_uit_badges(soup):
    for el in soup.find_all(class_=re.compile(r"status|label|badge|sticker|banner|ribbon|flag|tag", re.I)):
        tekst = _schoon(el.get_text(" "))
        if 0 < len(tekst) <= 40:
            s = normaliseer_status(tekst)
            if s and s != "beschikbaar":
                return s, tekst
    return None, ""


def parse_detail(html, url):
    soup = BeautifulSoup(html, "lxml")
    res = Resultaat(url=url)

    titel = _meta(soup, "og:title") or (soup.title.get_text() if soup.title else "")
    og_beschrijving = _meta(soup, "og:description") or _meta(soup, "description")
    res.foto_url = _meta(soup, "og:image")
    ld = _json_ld(soup)

    # JSON-LD adres (schema.org PostalAddress)
    # JSON-LD adres alleen van een woning (niet van het makelaarskantoor)
    for d in ld:
        types = d.get("@type", "")
        types = " ".join(types) if isinstance(types, list) else str(types)
        adr = d.get("address")
        if re.search(r"Residence|House|Apartment|Accommodation|Product|Offer", types) and isinstance(adr, dict):
            res.adres = res.adres or _schoon(str(adr.get("streetAddress", "")))
            res.postcode = res.postcode or _schoon(str(adr.get("postalCode", "")))
            plaats = _schoon(str(adr.get("addressLocality", "")))
            if plaats:
                res.woonplaats = res.woonplaats or (zoek_plaats(plaats) or plaats.title())
        if not res.foto_url and d.get("image"):
            img = d["image"]
            if isinstance(img, list) and img:
                img = img[0]
            if isinstance(img, dict):
                img = img.get("url", "")
            if isinstance(img, str):
                res.foto_url = img

    adres, postcode, plaats = parse_adres(titel, url)
    res.adres = res.adres or adres
    res.postcode = res.postcode or postcode
    res.woonplaats = res.woonplaats or plaats

    # Navigatie, kop- en voettekst weg voor het zoeken naar kenmerken
    for tag in soup(["script", "style", "noscript", "nav", "header", "footer", "form", "svg"]):
        tag.decompose()

    if not res.foto_url:
        for img in soup.find_all("img"):
            src = img.get("data-src") or img.get("src") or ""
            if src and not re.search(r"logo|icon|sprite|placeholder|\.svg", src, re.I):
                res.foto_url = src
                break
    if res.foto_url:
        res.foto_url = urljoin(url, res.foto_url)

    paren = _label_paren(soup)
    res.kenmerken = {label: waarde for (label, waarde) in paren.values()}

    controles = {
        "woonoppervlakte": r"\d\s*m", "perceel": r"\d\s*m", "inhoud": r"\d\s*m",
        "kamers": r"^\s*\d", "slaapkamers": r"^\s*\d", "bouwjaar": r"\d{4}",
        "prijs": r"\d|op aanvraag", "energielabel": r"\b[A-G]\b",
    }

    def veld(naam):
        # Labels in volgorde van LABELS (specifiek vóór algemeen), waarde moet kloppen
        for sleutel, doel in LABELS.items():
            if doel != naam or sleutel not in paren:
                continue
            waarde = paren[sleutel][1]
            if naam in controles and not re.search(controles[naam], waarde, re.I):
                continue
            return waarde
        return ""

    prijs_tekst = veld("prijs")
    huur_tekst = veld("huurprijs")
    if prijs_tekst:
        m = re.search(r"€\s*[\d.]+(,-|,\d\d)?(\s*(k\.\s?k\.?|v\.\s?o\.\s?n\.?|kosten koper|vrij op naam))?", prijs_tekst, re.I)
        res.prijs_tekst = m.group(0) if m else prijs_tekst[:120]
        res.vraagprijs, res.prijs_conditie = parse_prijs(prijs_tekst)
    if (huur_tekst and not prijs_tekst) or re.search(r"p\.?\s?m\.?\b|per maand|/\s?mnd", prijs_tekst or "", re.I):
        res.is_huur = True
    if re.search(r"\bte huur\b", titel, re.I) and not re.search(r"\bte koop\b", titel, re.I):
        res.is_huur = True
    if res.vraagprijs is None:
        # Prijs staat soms alleen in de beschrijving: 'Vraagprijs € 499.000,- Kosten koper'
        for d in ld:
            beschrijving = str(d.get("description", ""))
            m = re.search(r"(vraagprijs|koopsom)[^€]{0,20}€\s*[\d.]+[^.]{0,30}", beschrijving, re.I)
            if m:
                res.prijs_tekst = _schoon(m.group(0))
                res.vraagprijs, res.prijs_conditie = parse_prijs(m.group(0))
                break

    status_tekst = veld("status")
    status = normaliseer_status(status_tekst)
    if status is None:
        status, status_tekst = _status_uit_badges(soup)
    if status is None:
        s = normaliseer_status(og_beschrijving[:200]) if re.search(r"(is|wordt)\s+verkocht|verkocht|onder bod|onder optie", og_beschrijving[:200], re.I) else None
        if s:
            status, status_tekst = s, og_beschrijving[:60]
    if status is None and res.vraagprijs is not None:
        status, status_tekst = "beschikbaar", status_tekst or ""
    res.status = status
    res.status_tekst = status_tekst
    if status == "verhuurd":
        res.is_huur = True

    res.woonoppervlakte = _getal(veld("woonoppervlakte"))
    res.perceeloppervlakte = _getal(veld("perceel")) or None
    res.inhoud = _getal(veld("inhoud"))
    res.kamers = _getal(veld("kamers"))
    res.slaapkamers = _getal(veld("slaapkamers"))
    bouwjaar = _getal(veld("bouwjaar"))
    res.bouwjaar = bouwjaar if bouwjaar and 1000 < bouwjaar < 2100 else None
    label = veld("energielabel")
    m = re.search(r"\b([A-G](\+{1,5})?)\b", label or "")
    res.energielabel = m.group(1) if m else ""

    soort, soort_obj, type_ = veld("soort"), veld("soort_object"), veld("type")
    res.woningtype = normaliseer_type(soort, type_, soort_obj)
    if res.woningtype == "overig":
        res.woningtype = normaliseer_type(titel)
    if res.woningtype == "overig":
        # Laatste redmiddel: welk woningtype wordt het vaakst genoemd in de omschrijving?
        res.woningtype = type_uit_tekst(" ".join(f for f in _tekstlijst(soup) if len(f) > 80))
    if GEEN_WONING.search(f"{soort} {soort_obj} {type_}") and res.woningtype in ("overig",):
        res.geen_woning = True

    res.omschrijving = og_beschrijving[:500]
    return res
