"""Indeling van woningen in categorie (woning / appartement / bouwgrond / overig) en soort.

De soorten volgen de standaardlijsten die makelaars in hun software gebruiken
(o.a. Realworks): een lijst voor woonhuizen en een lijst voor appartementen.
"""
import re

# (code, label, patroon) – volgorde = prioriteit (specifiek vóór algemeen)
SOORTEN_WONING = [
    ("geschakeld-2-onder-1-kap", "Geschakelde 2-onder-1-kapwoning", r"geschakelde\s+(2|twee)\s?-?\s?onder\s?-?\s?(1|een)\s?-?\s?kap"),
    ("halfvrijstaand", "Halfvrijstaande woning", r"half\s?-?\s?vrijstaand"),
    ("2-onder-1-kap", "2-onder-1-kapwoning", r"(2|twee)\s?-?\s?onder\s?-?\s?(1|een)\s?-?\s?kap"),
    ("geschakeld", "Geschakelde woning", r"geschakeld"),
    ("vrijstaand", "Vrijstaande woning", r"vrijstaand"),
    ("hoekwoning", "Hoekwoning", r"hoekwoning|hoekhuis"),
    ("eindwoning", "Eindwoning", r"eindwoning"),
    ("tussenwoning", "Tussenwoning", r"tussenwoning|rijwoning|tussenhuis"),
    ("verspringend", "Verspringend", r"verspringend"),
]
SOORTEN_APPARTEMENT = [
    ("beneden-bovenwoning", "Beneden + bovenwoning", r"beneden\s?\+\s?boven|beneden-?\s+en\s+bovenwoning"),
    ("dubbel-benedenhuis", "Dubbel benedenhuis", r"dubbel\s+benedenhuis"),
    ("tussenverdieping", "Tussenverdieping", r"tussenverdieping"),
    ("penthouse", "Penthouse", r"penthouse"),
    ("maisonnette", "Maisonnette", r"maisonnette"),
    ("portiekwoning", "Portiekwoning", r"portiekwoning"),
    ("portiekflat", "Portiekflat", r"portiekflat"),
    ("galerijflat", "Galerijflat", r"galerijflat"),
    ("studentenkamer", "Studentenkamer", r"studentenkamer"),
    ("bovenwoning", "Bovenwoning", r"bovenwoning|bovenhuis"),
    ("benedenwoning", "Benedenwoning", r"benedenwoning|benedenhuis"),
]
# Volgorde in de keuzelijsten op de site (zoals de standaardlijsten van de makelaars)
WEERGAVE_WONING = ["vrijstaand", "geschakeld", "2-onder-1-kap", "tussenwoning", "hoekwoning", "eindwoning",
                   "halfvrijstaand", "geschakeld-2-onder-1-kap", "verspringend"]
WEERGAVE_APPARTEMENT = ["bovenwoning", "benedenwoning", "maisonnette", "galerijflat", "portiekflat",
                        "beneden-bovenwoning", "penthouse", "portiekwoning", "studentenkamer",
                        "dubbel-benedenhuis", "tussenverdieping"]
SOORT_KEUZES = [(c, l) for c, l, _ in SOORTEN_WONING + SOORTEN_APPARTEMENT]
SOORT_LABEL = dict(SOORT_KEUZES)

APPARTEMENT = re.compile(r"appartement|\bflat\b|studio|bovenwoning|benedenwoning|maisonnette|penthouse|portiek|galerij", re.I)
BOUWGROND = re.compile(r"bouwgrond|bouwkavel|\bkavel\b", re.I)
WOONHUIS = re.compile(
    r"woonhuis|eengezinswoning|herenhuis|villa|bungalow|landhuis|woonboerderij|boerderij|grachtenpand|"
    r"vrijstaand|2-onder|twee onder|tussenwoning|hoekwoning|eindwoning|geschakeld|halfvrijstaand|landgoed|"
    r"kwadrant|patiowoning|split-level|semi-bungalow|dijkwoning|woning", re.I,
)
OVERIG = re.compile(r"stacaravan|chalet|recreatie|vakantiewoning|woonwagen|woonboot|ligplaats", re.I)
VRIJSTAAND_SOORT = re.compile(r"villa|landhuis|woonboerderij|landgoed", re.I)

# Kenmerken waarin de makelaarssoftware het type vermeldt
VELDEN = ["type woning", "soort woonhuis", "soort woning", "soort appartement", "soort object", "type", "soort",
          "type object", "soortobject"]


def _normaal(tekst):
    tekst = (tekst or "").lower().replace("één", "een").replace("&eacute;", "e")
    return re.sub(r"\s+", " ", tekst)


def _zoek(lijst, tekst):
    for code, _label, patroon in lijst:
        if re.search(patroon, tekst):
            return code
    return ""


def _meest_genoemd(lijst, tekst):
    """Voor lopende tekst: de soort die het vaakst genoemd wordt (alleen bij een duidelijke winnaar)."""
    telling = {code: len(re.findall(patroon, tekst)) for code, _l, patroon in lijst}
    beste = max(telling, key=telling.get)
    if telling[beste] and list(telling.values()).count(telling[beste]) == 1:
        return beste
    return ""


def classificeer(kenmerken=None, titel="", omschrijving=""):
    """Geeft (categorie, soort). Soort is '' als die niet te bepalen is."""
    kenmerken = {(k or "").lower(): v for k, v in (kenmerken or {}).items()}
    velden = _normaal(" | ".join(kenmerken[v] for v in VELDEN if v in kenmerken))
    titel, omschrijving = _normaal(titel), _normaal(omschrijving)

    # 1. Soort uit de kenmerken (het betrouwbaarst)
    soort = _zoek(SOORTEN_APPARTEMENT, velden)
    if soort:
        return "appartement", soort
    soort = _zoek(SOORTEN_WONING, velden)
    if soort:
        return "woning", soort

    # 2. Categorie uit de kenmerken, anders uit de titel
    categorie = ""
    for bron in (velden, titel):
        if not bron:
            continue
        if BOUWGROND.search(bron):
            categorie = "bouwgrond"
        elif APPARTEMENT.search(bron):
            categorie = "appartement"
        elif OVERIG.search(bron):
            categorie = "overig"
        elif WOONHUIS.search(bron):
            categorie = "woning"
        if categorie:
            break

    # 3. Soort uit titel of omschrijving binnen de categorie
    if categorie in ("woning", ""):
        soort = _zoek(SOORTEN_WONING, titel) or _meest_genoemd(SOORTEN_WONING, omschrijving)
        if not soort and VRIJSTAAND_SOORT.search(velden):
            soort = "vrijstaand"  # villa, landhuis, woonboerderij
        if soort:
            return "woning", soort
    if categorie in ("appartement", ""):
        soort = _zoek(SOORTEN_APPARTEMENT, titel) or _meest_genoemd(SOORTEN_APPARTEMENT, omschrijving)
        if soort:
            return "appartement", soort
    if not categorie:
        if APPARTEMENT.search(omschrijving[:300]):
            categorie = "appartement"
        elif WOONHUIS.search(omschrijving[:300]):
            categorie = "woning"
        else:
            categorie = "overig"
    return categorie, ""
