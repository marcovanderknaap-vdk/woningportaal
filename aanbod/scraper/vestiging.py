"""Bepalen welk kantoor (vestiging) van een makelaar een woning aanbiedt.

1. Van de pagina: het kantoor waarvan het telefoonnummer duidelijk vaker op de woningpagina
   staat dan dat van de andere kantoren (de algemene contactlijst in de voettekst telt voor
   alle kantoren even vaak mee en valt dus weg).
2. Anders: het dichtstbijzijnde kantoor, berekend vanaf de locatie van de woning.
"""
import math
import re


def _nationaal(telefoon):
    cijfers = re.sub(r"\D", "", telefoon or "")
    if cijfers.startswith("0031"):
        cijfers = "0" + cijfers[4:]
    elif cijfers.startswith("31") and len(cijfers) == 11:
        cijfers = "0" + cijfers[2:]
    return cijfers


def _tel(cijfers, telefoon):
    nat = _nationaal(telefoon)
    if len(nat) < 9:
        return 0
    # '0113250555', maar ook internationaal '31113250555' / '0031113250555'
    return cijfers.count(nat) + cijfers.count("31" + nat[1:])


def van_pagina(vestigingen, paginacijfers):
    if not paginacijfers or len(vestigingen) < 2:
        return None
    tellingen = [(_tel(paginacijfers, v.telefoon), v) for v in vestigingen]
    hoogste = max(t for t, _ in tellingen)
    winnaars = [v for t, v in tellingen if t == hoogste]
    if hoogste > 0 and len(winnaars) == 1 and hoogste > min(t for t, _ in tellingen):
        return winnaars[0]
    return None


def _afstand_km(lat1, lon1, lat2, lon2):
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def dichtstbij(vestigingen, woning):
    met_locatie = [v for v in vestigingen if v.lat is not None and v.lon is not None]
    if woning.lat is None or not met_locatie:
        # Zonder coördinaten: kantoor in dezelfde plaats, als dat er is
        zelfde = [v for v in vestigingen if v.plaats.lower() == (woning.woonplaats or "").lower()]
        return zelfde[0] if zelfde else None
    return min(met_locatie, key=lambda v: _afstand_km(woning.lat, woning.lon, v.lat, v.lon))


def bepaal(woning, paginacijfers=None):
    """Geeft (vestiging, bron) terug; bron is 'enige', 'pagina' of 'afstand'."""
    vestigingen = list(woning.makelaar.vestigingen.all())
    if not vestigingen:
        return None, ""
    if len(vestigingen) == 1:
        return vestigingen[0], "enige"
    v = van_pagina(vestigingen, paginacijfers)
    if v:
        return v, "pagina"
    v = dichtstbij(vestigingen, woning)
    return (v, "afstand") if v else (None, "")


def koppel(woning, paginacijfers=None, opslaan=True):
    """Zet woning.vestiging. Een eerder van de pagina gelezen kantoor wordt niet door een gok overschreven."""
    v, bron = bepaal(woning, paginacijfers)
    if bron == "afstand" and woning.vestiging_bron == "pagina" and woning.vestiging_id:
        return False
    if (woning.vestiging_id, woning.vestiging_bron) == ((v.pk if v else None), bron):
        return False
    woning.vestiging, woning.vestiging_bron = v, bron
    if opslaan and woning.pk:
        woning.save(update_fields=["vestiging", "vestiging_bron"])
    return True
