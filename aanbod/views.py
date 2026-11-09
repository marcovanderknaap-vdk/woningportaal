import json
from collections import Counter

from django.conf import settings
from django.shortcuts import get_object_or_404, render

from .models import Makelaar, Woning

PRIJSKLASSEN = [
    ("0-200000", "tot € 200.000", 0, 200_000),
    ("200000-300000", "€ 200.000 – € 300.000", 200_000, 300_000),
    ("300000-400000", "€ 300.000 – € 400.000", 300_000, 400_000),
    ("400000-500000", "€ 400.000 – € 500.000", 400_000, 500_000),
    ("500000-750000", "€ 500.000 – € 750.000", 500_000, 750_000),
    ("750000-", "vanaf € 750.000", 750_000, None),
]


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
        "type": w.woningtype,
        "typeLabel": w.get_woningtype_display(),
        "opp": w.woonoppervlakte,
        "perceel": w.perceeloppervlakte,
        "kamers": w.kamers,
        "label": w.energielabel,
        "nieuw": w.is_nieuw,
        "sinds": w.eerst_gezien.date().isoformat(),
        "foto": _media_url(request, w.foto) or w.foto_bron_url,
        "url": f"{basis}woning/{w.pk}/",
        "makelaar": w.makelaar.naam,
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
            "types": Woning.Type.choices,
            "statussen": Woning.Status.choices,
            "makelaars_aantal": Makelaar.objects.filter(actief=True).count(),
        },
    )


def detail(request, pk):
    woning = get_object_or_404(Woning.objects.select_related("makelaar"), pk=pk, verborgen=False)
    hoofd = [
        ("Vraagprijs", woning.prijs_tekst or "Prijs op aanvraag"),
        ("Status", woning.get_status_display()),
        ("Soort", woning.get_woningtype_display()),
        ("Woonoppervlakte", f"{woning.woonoppervlakte} m²" if woning.woonoppervlakte else ""),
        ("Perceel", f"{woning.perceeloppervlakte:,} m²".replace(",", ".") if woning.perceeloppervlakte else ""),
        ("Inhoud", f"{woning.inhoud} m³" if woning.inhoud else ""),
        ("Kamers", str(woning.kamers) if woning.kamers else ""),
        ("Slaapkamers", str(woning.slaapkamers) if woning.slaapkamers else ""),
        ("Bouwjaar", str(woning.bouwjaar) if woning.bouwjaar else ""),
        ("Energielabel", woning.energielabel),
    ]
    return render(
        request,
        "aanbod/detail.html",
        {
            "woning": woning,
            "hoofd": [(k, v) for k, v in hoofd if v],
            "foto": _media_url(request, woning.foto) or woning.foto_bron_url,
        },
    )


def makelaars(request):
    lijst = list(Makelaar.objects.filter(actief=True))
    for m in lijst:
        m.aantal = Woning.objects.zichtbaar().filter(makelaar=m).count()
    return render(request, "aanbod/makelaars.html", {"makelaars": lijst})
