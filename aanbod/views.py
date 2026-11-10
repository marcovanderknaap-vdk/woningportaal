import json
from collections import Counter

from django.conf import settings
import mimetypes
from pathlib import Path

from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render

from .models import Makelaar, Woning
from .scraper.soort import SOORT_LABEL, WEERGAVE_APPARTEMENT, WEERGAVE_WONING

PRIJSKLASSEN = [
    ("0-200000", "tot € 200.000", 0, 200_000),
    ("200000-300000", "€ 200.000 – € 300.000", 200_000, 300_000),
    ("300000-400000", "€ 300.000 – € 400.000", 300_000, 400_000),
    ("400000-500000", "€ 400.000 – € 500.000", 400_000, 500_000),
    ("500000-750000", "€ 500.000 – € 750.000", 500_000, 750_000),
    ("750000-", "vanaf € 750.000", 750_000, None),
]

CATEGORIEEN = [("woning", "Woning"), ("appartement", "Appartement"), ("bouwgrond", "Bouwgrond")]
SOORTEN = {
    "woning": [(c, SOORT_LABEL[c]) for c in WEERGAVE_WONING],
    "appartement": [(c, SOORT_LABEL[c]) for c in WEERGAVE_APPARTEMENT],
}
PER_PAGINA = [12, 24, 48, 96]


def _media_url(request, bestand):
    if not bestand:
        return ""
    return getattr(request, "basis_url", "/") + settings.MEDIA_URL.lstrip("/") + bestand.name


def woning_json(request, w):
    basis = getattr(request, "basis_url", "/")
    return {
        "id": w.pk,
        "adres": w.adres,
        "plaats": w.woonplaats,
        "postcode": w.postcode,
        "prijs": w.vraagprijs,
        "prijsTekst": w.prijs_tekst,
        "conditie": w.prijs_conditie,
        "status": w.status,
        "statusLabel": w.get_status_display(),
        "categorie": w.categorie,
        "soort": w.soort,
        "soortLabel": w.soort_label,
        "opp": w.woonoppervlakte,
        "perceel": w.perceeloppervlakte,
        "kamers": w.kamers,
        "slaapkamers": w.slaapkamers,
        "label": w.energielabel,
        "nieuw": w.is_nieuw,
        "sinds": w.eerst_gezien.date().isoformat(),
        "foto": _media_url(request, w.foto) or w.foto_bron_url,
        "url": f"{basis}woning/{w.pk}/",
        "makelaar": w.makelaar.naam,
        "lat": round(w.lat, 6) if w.lat is not None else None,
        "lon": round(w.lon, 6) if w.lon is not None else None,
        "logo": _media_url(request, w.makelaar.logo),
    }


def index(request):
    woningen = list(Woning.objects.zichtbaar().select_related("makelaar"))
    data = [woning_json(request, w) for w in woningen]
    plaatsen = Counter(w.woonplaats for w in woningen if w.woonplaats)
    return render(
        request,
        "aanbod/index.html",
        {
            "woningen_json": json.dumps(data, ensure_ascii=False),
            "aantal": len(data),
            "plaatsen": sorted(plaatsen.items()),
            "prijsklassen": PRIJSKLASSEN,
            "categorieen": CATEGORIEEN,
            "soorten": SOORTEN,
            "soorten_json": json.dumps(SOORTEN, ensure_ascii=False),
            "per_pagina": PER_PAGINA,
            "statussen": Woning.Status.choices,
            "makelaars_aantal": Makelaar.objects.filter(actief=True).count(),
            "menu_actief": "koopwoningen",
        },
    )


def detail(request, pk):
    woning = get_object_or_404(Woning.objects.select_related("makelaar"), pk=pk, verborgen=False)
    hoofd = [
        ("Status", woning.get_status_display()),
        ("Soort appartement" if woning.categorie == "appartement" else "Soort woning" if woning.categorie == "woning" else "Soort",
         woning.soort_label),
        ("Woonoppervlakte", f"{woning.woonoppervlakte} m²" if woning.woonoppervlakte else ""),
        ("Perceel", f"{woning.perceeloppervlakte:,} m²".replace(",", ".") if woning.perceeloppervlakte else ""),
        ("Inhoud", f"{woning.inhoud} m³" if woning.inhoud else ""),
        ("Kamers", str(woning.kamers) if woning.kamers else ""),
        ("Slaapkamers", str(woning.slaapkamers) if woning.slaapkamers else ""),
        ("Bouwjaar", str(woning.bouwjaar) if woning.bouwjaar else ""),
        ("Energielabel", woning.energielabel),
    ]
    alle_kantoren = list(woning.makelaar.vestigingen.all())
    kantoor = woning.vestiging if woning.vestiging in alle_kantoren else None
    if kantoor is None and alle_kantoren:
        # Nog niet bepaald: zelfde plaats of het eerste kantoor, als dichtstbijzijnde
        from .scraper.vestiging import dichtstbij
        kantoor = dichtstbij(alle_kantoren, woning) or alle_kantoren[0]
    return render(
        request,
        "aanbod/detail.html",
        {
            "woning": woning,
            "hoofd": [(k, v) for k, v in hoofd if v],
            "foto": _media_url(request, woning.foto) or woning.foto_bron_url,
            "logo": _media_url(request, woning.makelaar.logo),
            # Het aanbiedende kantoor; de overige vestigingen ingeklapt eronder
            "kantoor": kantoor,
            "menu_actief": "koopwoningen",
            "andere_kantoren": [v for v in alle_kantoren if v != kantoor],
        },
    )


def makelaars(request):
    lijst = list(Makelaar.objects.filter(actief=True))
    for m in lijst:
        m.aantal = Woning.objects.zichtbaar().filter(makelaar=m).count()
        m.logo_url = _media_url(request, m.logo)
    return render(request, "aanbod/makelaars.html", {"makelaars": lijst, "menu_actief": "makelaars"})


def over(request):
    zichtbaar = Woning.objects.zichtbaar()
    return render(
        request,
        "aanbod/over.html",
        {
            "menu_actief": "over",
            "aantal_makelaars": Makelaar.objects.filter(actief=True).count(),
            "aantal_woningen": zichtbaar.count(),
            "aantal_plaatsen": zichtbaar.exclude(woonplaats="").values("woonplaats").distinct().count(),
        },
    )


def robots_txt(request):
    if settings.PORTAAL_INDEXEREN:
        regels = ["User-agent: *", "Disallow: /beheer/"]
    else:
        regels = ["User-agent: *", "Disallow: /"]
    return HttpResponse("\n".join(regels) + "\n", content_type="text/plain")


# Website-iconen met vaste namen, geserveerd vanuit de hoofdmap van de site
WEBSITE_BESTANDEN = {"favicon.ico", "favicon.svg", "apple-touch-icon.png", "icon-192.png", "icon-512.png", "og-image.png"}
WEBSITE_MAP = Path(__file__).resolve().parent / "static" / "website"


def website_bestand(request, naam):
    if naam not in WEBSITE_BESTANDEN:
        raise Http404
    pad = WEBSITE_MAP / naam
    type_ = "image/x-icon" if naam.endswith(".ico") else mimetypes.guess_type(naam)[0]
    return FileResponse(open(pad, "rb"), content_type=type_)


def manifest(request):
    basis = getattr(request, "basis_url", "/")
    return JsonResponse(
        {
            "name": settings.PORTAAL_NAAM,
            "short_name": settings.PORTAAL_NAAM,
            "lang": "nl",
            "start_url": basis,
            "display": "browser",
            "theme_color": "#0A3A86",
            "background_color": "#FFFFFF",
            "icons": [
                {"src": f"{basis}icon-192.png", "sizes": "192x192", "type": "image/png"},
                {"src": f"{basis}icon-512.png", "sizes": "512x512", "type": "image/png"},
            ],
        },
        content_type="application/manifest+json",
    )
