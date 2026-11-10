"""Template-hulpjes voor Weune."""
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from django import template

register = template.Library()


@register.filter
def via_weune(url, plek="woningpagina"):
    """Voeg UTM-parameters toe aan een link naar een makelaarssite, zodat de makelaar in zijn
    statistieken ziet hoeveel bezoekers via Weune komen (utm_content = waar op Weune geklikt is).
    Bestaande parameters en een #anker blijven behouden."""
    if not url:
        return url
    delen = urlsplit(url)
    params = [(k, v) for k, v in parse_qsl(delen.query, keep_blank_values=True) if not k.startswith("utm_")]
    params += [("utm_source", "weune"), ("utm_medium", "referral"),
               ("utm_campaign", "woningaanbod"), ("utm_content", plek)]
    return urlunsplit((delen.scheme, delen.netloc, delen.path or "/", urlencode(params), delen.fragment))
