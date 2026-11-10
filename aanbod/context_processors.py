import json

from django.conf import settings


def portaal(request):
    return {
        "PORTAAL_NAAM": settings.PORTAAL_NAAM,
        "NIEUW_DAGEN": settings.NIEUW_DAGEN,
        "INDEXEREN": settings.PORTAAL_INDEXEREN,
        "SITE_URL": settings.PORTAAL_SITE_URL,
        # Bij de statische export wordt dit het pad van de GitHub Pages-site
        "BASIS": getattr(request, "basis_url", "/"),
        "BASIS_JSON": json.dumps(getattr(request, "basis_url", "/")),
        "KAART_JSON": json.dumps({
            "tegels": settings.KAART_TEGELS_URL,
            "attributie": settings.KAART_ATTRIBUTIE,
            "maxZoom": settings.KAART_MAX_ZOOM,
        }),
        "STATISCH": getattr(request, "statisch", False),
    }
