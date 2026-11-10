"""Het logo van een makelaar automatisch van diens website halen."""
import io
import logging
import re
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup
from django.core.files.base import ContentFile
from PIL import Image

log = logging.getLogger("aanbod.scraper")

# Keurmerken en andere logo's die niet van de makelaar zelf zijn
GEEN_EIGEN_LOGO = re.compile(
    r"nvm|vbo|mva|funda|vastgoedpro|taxatheek|nwwi|keurmerk|google|facebook|instagram|linkedin|whatsapp|"
    r"youtube|twitter|pinterest|cookie|klantenvertellen|kiyoh|trustpilot|icon|sprite|placeholder",
    re.I,
)
WIT = re.compile(r"(^|[-_/.\s])(wit|white|negatief|negative|inverse|light)([-_/.\s]|$)", re.I)


def _kandidaten(soup, basis):
    """Afbeeldingen met 'logo' in src/alt/class/id, die in de kop eerst."""
    gevonden = []
    for img in soup.find_all(["img", "image"]):
        src = img.get("src") or img.get("data-src") or img.get("href") or img.get("xlink:href") or ""
        if not src or src.startswith("data:"):
            continue
        ouders = " ".join(
            " ".join(p.get("class", [])) + " " + (p.get("id") or "") for p in img.parents if hasattr(p, "get")
        )
        kenmerken = f"{src} {img.get('alt', '')} {' '.join(img.get('class', []))} {img.get('id', '')}"
        link = img.find_parent("a")
        naar_home = bool(link and urlsplit(urljoin(basis, link.get("href", ""))).path in ("", "/"))
        if not re.search(r"logo|brand", (kenmerken + " " + ouders[:300]), re.I) and not naar_home:
            continue
        if GEEN_EIGEN_LOGO.search(kenmerken):
            continue
        in_kop = img.find_parent(["header", "nav"]) is not None or re.search(r"header|navbar|top", ouders, re.I)
        in_voet = img.find_parent("footer") is not None or re.search(r"footer", ouders, re.I)
        score = (0 if in_kop else 1) + (2 if in_voet else 0) + (3 if WIT.search(kenmerken) else 0)
        gevonden.append((score, len(gevonden), urljoin(basis, src)))
    return [url for _, _, url in sorted(gevonden)]


def zoek_logo_url(fetcher, makelaar):
    basis = makelaar.website or makelaar.aanbod_url
    parts = urlsplit(basis)
    start = f"{parts.scheme}://{parts.netloc}/"
    r = fetcher.get(start)
    if r.status_code != 200:
        return ""
    soup = BeautifulSoup(r.text, "lxml")
    kandidaten = _kandidaten(soup, r.url)
    return kandidaten[0] if kandidaten else ""


def haal_logo(fetcher, makelaar):
    """Zoek en bewaar het logo. Geeft True terug als dat gelukt is."""
    url = zoek_logo_url(fetcher, makelaar)
    if not url:
        return False
    r = fetcher.get(url, check_robots=False, binary=True)
    if r.status_code != 200 or not r.content:
        return False
    naam = f"makelaar-{makelaar.pk}"
    inhoud = r.content
    if url.lower().split("?")[0].endswith(".svg") or b"<svg" in inhoud[:500]:
        bestand = f"{naam}.svg"
    else:
        img = Image.open(io.BytesIO(inhoud))
        img.thumbnail((600, 200))
        buf = io.BytesIO()
        img.save(buf, "PNG", optimize=True)
        inhoud, bestand = buf.getvalue(), f"{naam}.png"
    if makelaar.logo:
        makelaar.logo.delete(save=False)
    makelaar.logo.save(bestand, ContentFile(inhoud), save=False)
    makelaar.logo_bron_url = url
    makelaar.save(update_fields=["logo", "logo_bron_url"])
    return True
