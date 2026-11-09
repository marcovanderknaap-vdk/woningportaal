"""Woonplaatsen in Zeeland, gebruikt om de woonplaats uit titels/URL's te herkennen.

Woonplaatsen buiten Zeeland worden ook herkend (zie ``detail.py``), maar deze
lijst maakt het herkennen van meerwoordige namen (Oost-Souburg, Sas van Gent,
's-Heer Arendskerke) betrouwbaar.
"""
import re
import unicodedata

ZEEUWSE_PLAATSEN = [
    # Middelburg
    "Middelburg", "Arnemuiden", "Nieuw- en Sint Joosland", "Kleverskerke",
    # Vlissingen
    "Vlissingen", "Oost-Souburg", "West-Souburg", "Souburg", "Ritthem",
    # Veere
    "Veere", "Domburg", "Westkapelle", "Zoutelande", "Vrouwenpolder", "Serooskerke",
    "Oostkapelle", "Aagtekerke", "Grijpskerke", "Meliskerke", "Biggekerke",
    "Koudekerke", "Dishoek", "Gapinge", "Sint Laurens", "Valkenisse",
    # Goes
    "Goes", "Kloetinge", "Kattendijke", "'s-Heer Arendskerke", "'s-Heer Hendrikskinderen",
    "Wilhelminadorp", "Wolphaartsdijk", "Oud-Sabbinge",
    # Borsele
    "Heinkenszand", "'s-Gravenpolder", "'s-Heerenhoek", "Baarland", "Borssele",
    "Driewegen", "Ellewoutsdijk", "Hoedekenskerke", "Kwadendamme", "Lewedorp",
    "Nieuwdorp", "Nisse", "Oudelande", "Ovezande", "Sinoutskerke",
    # Kapelle
    "Kapelle", "Biezelinge", "Schore", "Wemeldinge", "Eversdijk",
    # Reimerswaal
    "Yerseke", "Kruiningen", "Krabbendijke", "Rilland", "Bath", "Hansweert", "Waarde",
    # Noord-Beveland
    "Kortgene", "Wissenkerke", "Kamperland", "Colijnsplaat", "Kats", "Geersdijk",
    # Schouwen-Duiveland
    "Zierikzee", "Brouwershaven", "Bruinisse", "Burgh-Haamstede", "Haamstede", "Burgh",
    "Renesse", "Noordwelle", "Scharendijke", "Ellemeet", "Kerkwerve", "Nieuwerkerk",
    "Oosterland", "Ouwerkerk", "Dreischor", "Zonnemaire", "Noordgouwe", "Sirjansland",
    "Elkerzee", "Looperskapelle", "Schuddebeurs", "Viane", "Duivendijke",
    # Tholen
    "Tholen", "Sint-Maartensdijk", "Sint Philipsland", "Stavenisse", "Oud-Vossemeer",
    "Poortvliet", "Scherpenisse", "Sint-Annaland", "Anna Jacobapolder",
    # Sluis
    "Oostburg", "Sluis", "Aardenburg", "Breskens", "Cadzand", "Cadzand-Bad", "Groede",
    "IJzendijke", "Retranchement", "Schoondijke", "Sint Kruis", "Waterlandkerkje",
    "Zuidzande", "Nieuwvliet", "Nieuwvliet-Bad", "Hoofdplaat", "Eede", "Heille",
    "Sint Anna ter Muiden",
    # Terneuzen
    "Terneuzen", "Sas van Gent", "Axel", "Hoek", "Sluiskil", "Zaamslag", "Westdorpe",
    "Philippine", "Biervliet", "Koewacht", "Overslag", "Zuiddorpe", "Spui", "Absdale",
    # Hulst
    "Hulst", "Hontenisse", "Kloosterzande", "Clinge", "Graauw", "Heikant", "Kapellebrug",
    "Lamswaarde", "Nieuw-Namen", "Ossenisse", "Sint Jansteen", "Terhole", "Vogelwaarde",
    "Walsoorden", "Hengstdijk", "Kuitaart",
]


def slug(tekst: str) -> str:
    """'s-Heer Arendskerke -> s-heer-arendskerke"""
    tekst = unicodedata.normalize("NFKD", tekst).encode("ascii", "ignore").decode()
    tekst = tekst.lower().replace("'", "")
    return re.sub(r"[^a-z0-9]+", "-", tekst).strip("-")


# slug -> nette naam; langste eerst zodat 'oost-souburg' vóór 'souburg' gaat
_PLAATS_PER_SLUG = {slug(p): p for p in ZEEUWSE_PLAATSEN}
_SLUGS_LANGSTE_EERST = sorted(_PLAATS_PER_SLUG, key=len, reverse=True)


def zoek_plaats(tekst: str, laatste=True):
    """Zoek een Zeeuwse woonplaats als heel woord in de tekst.

    Bij meerdere treffers wint standaard de laatste (in titels staat de
    plaats achter de straatnaam). Geeft de nette naam terug of None.
    """
    if not tekst:
        return None
    s = "-" + slug(tekst) + "-"
    treffers = []
    for ps in _SLUGS_LANGSTE_EERST:
        start = 0
        while True:
            i = s.find("-" + ps + "-", start)
            if i < 0:
                break
            # Niet meetellen als dit deel is van een langere, al gevonden naam
            if not any(a <= i < b for a, b, _ in treffers):
                treffers.append((i, i + len(ps) + 1, _PLAATS_PER_SLUG[ps]))
            start = i + 1
    if not treffers:
        return None
    treffers.sort()
    return treffers[-1][2] if laatste else treffers[0][2]
