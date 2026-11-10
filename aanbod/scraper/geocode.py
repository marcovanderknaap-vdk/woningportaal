"""Coördinaten (en zo nodig de postcode) van een adres opzoeken bij de PDOK Locatieserver.

PDOK is de geo-dienstverlening van de Nederlandse overheid: gratis, zonder account,
en gebaseerd op de officiële adressenregistratie (BAG).
"""
import logging
import re
from datetime import timedelta

import requests
from django.conf import settings
from django.utils import timezone

log = logging.getLogger("aanbod.scraper")

PDOK_URL = "https://api.pdok.nl/bzk/locatieserver/search/v3_1/free"
OPNIEUW_PROBEREN_NA = timedelta(days=14)


def _norm(tekst):
    return re.sub(r"[^a-z0-9]", "", (tekst or "").lower().replace("'s-", "s").replace("-", ""))


def zoek(adres, postcode="", woonplaats="", sessie=None):
    """Geeft (lat, lon, postcode) of None. Alleen een treffer op exact adres in dezelfde woonplaats telt."""
    if not adres:
        return None
    q = " ".join(x for x in (adres, postcode, woonplaats) if x)
    http = sessie or requests
    r = http.get(
        PDOK_URL,
        params={"q": q, "fq": "type:adres", "rows": 3,
                "fl": "centroide_ll,woonplaatsnaam,postcode,straatnaam,huisnummer,huisletter,huisnummertoevoeging"},
        headers={"User-Agent": settings.SCRAPER_USER_AGENT},
        timeout=20,
    )
    r.raise_for_status()
    huisnummer = re.search(r"\d+", adres)
    for doc in r.json().get("response", {}).get("docs", []):
        if woonplaats and _norm(doc.get("woonplaatsnaam")) != _norm(woonplaats):
            continue
        if huisnummer and str(doc.get("huisnummer")) != huisnummer.group(0):
            continue
        if _norm(doc.get("straatnaam")) not in _norm(adres):
            continue
        m = re.match(r"POINT\(([-\d.]+) ([-\d.]+)\)", doc.get("centroide_ll", ""))
        if m:
            pc = doc.get("postcode") or ""
            pc = f"{pc[:4]} {pc[4:]}" if len(pc) == 6 else pc
            return float(m.group(2)), float(m.group(1)), pc
    return None


def geocodeer(woning, sessie=None, opslaan=True):
    """Vul lat/lon (en ontbrekende postcode) van een woning. Geeft True bij succes."""
    woning.geo_gecontroleerd = timezone.now()
    velden = ["geo_gecontroleerd"]
    try:
        res = zoek(woning.adres, woning.postcode, woning.woonplaats, sessie)
    except requests.RequestException as exc:
        log.warning("PDOK niet bereikbaar voor %s: %s", woning, exc)
        res = None
    if res:
        woning.lat, woning.lon, pc = res
        velden += ["lat", "lon"]
        if pc and not woning.postcode:
            woning.postcode = pc
            velden.append("postcode")
    if opslaan and woning.pk:
        woning.save(update_fields=velden)
    return bool(res)


def te_geocoderen(qs):
    """Woningen zonder coördinaten die nog niet (of lang geleden) zijn opgezocht."""
    from django.db.models import Q

    grens = timezone.now() - OPNIEUW_PROBEREN_NA
    return qs.filter(lat__isnull=True).filter(Q(geo_gecontroleerd__isnull=True) | Q(geo_gecontroleerd__lt=grens))
