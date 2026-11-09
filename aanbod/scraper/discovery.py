"""Het vinden van links naar woningdetailpagina's bij een makelaar."""
import logging
import re
from collections import Counter
from urllib.parse import urldefrag, urljoin, urlsplit

from bs4 import BeautifulSoup

log = logging.getLogger("aanbod.scraper")

# Paden die vrijwel nooit een woning zijn
UITSLUITEN = re.compile(
    r"/(tags?|nieuws|blog|blogs|kennisbank|kenniscentrum|contact|diensten|over-ons|team|"
    r"medewerkers?|vacatures?|privacy|cookie|disclaimer|werkgebied(en)?|reviews?|beoordelingen|"
    r"category|author|wp-content|wp-json|feed|pdf|zoekopdracht|inloggen|login|mijn-?)\b",
    re.I,
)
PAGINERING = re.compile(r"(/page/\d+/?$|/pagina-\d+/?$|[?&](page|p|pagina|paged|pg)=\d+)", re.I)
BESTAND = re.compile(r"\.(pdf|jpe?g|png|webp|gif|zip|docx?|xml|json)$", re.I)


def _host(url):
    return urlsplit(url).netloc.lower().removeprefix("www.")


def normaliseer(url):
    return urldefrag(url)[0].strip()


def lijkt_op_woning(url):
    """Heuristiek: laatste padsegment bevat een huisnummer en minstens één koppelteken."""
    parts = urlsplit(url)
    if parts.query or BESTAND.search(parts.path) or UITSLUITEN.search(parts.path):
        return False
    if PAGINERING.search(url):
        return False
    segment = parts.path.rstrip("/").rsplit("/", 1)[-1]
    return bool(re.search(r"\d", segment)) and "-" in segment and len(segment) >= 8


def kies_woninglinks(links, patroon=None, basis_url=None):
    links = {normaliseer(l) for l in links}
    if basis_url:
        links.discard(normaliseer(basis_url))
    if patroon:
        regex = re.compile(patroon)
        return sorted(l for l in links if regex.search(l))
    kandidaten = [l for l in links if lijkt_op_woning(l)]
    if not kandidaten:
        return []
    # Houd de grootste groep met hetzelfde eerste padsegment-niveau over
    def groep(url):
        segmenten = [s for s in urlsplit(url).path.split("/") if s]
        return (len(segmenten), segmenten[0] if len(segmenten) > 1 else "")

    telling = Counter(groep(l) for l in kandidaten)
    beste, aantal = telling.most_common(1)[0]
    # Kleine groepen naast een duidelijke hoofdgroep weglaten
    gekozen = [l for l in kandidaten if groep(l) == beste or telling[groep(l)] >= max(3, aantal * 0.3)]
    return sorted(gekozen)


def _links_op_pagina(html, pagina_url):
    soup = BeautifulSoup(html, "lxml")
    host = _host(pagina_url)
    uit = set()
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if href.startswith(("mailto:", "tel:", "javascript:", "#")):
            continue
        absoluut = urljoin(pagina_url, href)
        if _host(absoluut) == host and absoluut.startswith("http"):
            uit.add(normaliseer(absoluut))
    return uit


def _paginering_links(links, start_url):
    basis = urlsplit(start_url).path.rstrip("/")
    basis = re.sub(r"/(page/\d+|pagina-\d+)$", "", basis)
    gevonden = set()
    for l in links:
        parts = urlsplit(l)
        if PAGINERING.search(l) and parts.path.rstrip("/").startswith(basis):
            gevonden.add(l)
    return gevonden


def via_aanbodpagina(fetcher, start_url, patroon=None, max_paginas=30, logregels=None):
    """Loop de overzichtspagina('s) inclusief paginering door."""
    te_doen = [normaliseer(start_url)]
    gezien = set()
    alle_links = set()
    while te_doen and len(gezien) < max_paginas:
        url = te_doen.pop(0)
        if url in gezien:
            continue
        gezien.add(url)
        r = fetcher.get(url)
        if r.status_code != 200:
            if logregels is not None:
                logregels.append(f"Overzichtspagina {url} gaf HTTP {r.status_code}")
            continue
        links = _links_op_pagina(r.text, r.url)
        alle_links |= links
        for p in sorted(_paginering_links(links, start_url)):
            if p not in gezien and p not in te_doen:
                te_doen.append(p)
    woningen = kies_woninglinks(alle_links, patroon, start_url)
    if logregels is not None:
        logregels.append(f"{len(gezien)} overzichtspagina('s) bekeken, {len(woningen)} woninglinks gevonden")
    return woningen


SITEMAP_WONING = re.compile(r"(wonen|woning|huis|huizen|residential|property|object|aanbod|koop)", re.I)


def via_sitemap(fetcher, sitemap_url, patroon=None, logregels=None, _diepte=0):
    r = fetcher.get(sitemap_url)
    if r.status_code != 200:
        if logregels is not None:
            logregels.append(f"Sitemap {sitemap_url} gaf HTTP {r.status_code}")
        return []
    soup = BeautifulSoup(r.content, "xml")
    locs = [l.get_text(strip=True) for l in soup.find_all("loc")]
    if soup.find("sitemapindex") and _diepte < 2:
        uit = set()
        for sub in locs:
            if SITEMAP_WONING.search(sub.rsplit("/", 1)[-1]) and "nieuwbouw" not in sub and "bog" not in sub:
                uit |= set(via_sitemap(fetcher, sub, patroon, logregels, _diepte + 1))
        return sorted(uit)
    woningen = kies_woninglinks(locs, patroon, sitemap_url)
    if logregels is not None:
        logregels.append(f"Sitemap {sitemap_url}: {len(locs)} URL's, {len(woningen)} woninglinks")
    return woningen


def vind_woninglinks(fetcher, makelaar, logregels=None):
    from ..models import Makelaar

    links = set()
    for url in makelaar.alle_aanbod_urls():
        is_sitemap = url.lower().split("?")[0].endswith(".xml") or (
            url == makelaar.aanbod_url and makelaar.effectief_bron_type == Makelaar.BronType.SITEMAP
        )
        if is_sitemap:
            links |= set(via_sitemap(fetcher, url, makelaar.link_patroon or None, logregels))
        else:
            links |= set(
                via_aanbodpagina(fetcher, url, makelaar.link_patroon or None, makelaar.max_paginas, logregels)
            )
    return sorted(links)
