import requests
from django.core.management.base import BaseCommand

from aanbod.models import Woning
from aanbod.scraper.geocode import geocodeer, te_geocoderen


class Command(BaseCommand):
    help = "Zoek coördinaten op voor woningen die nog niet op de kaart staan (PDOK Locatieserver)."

    def add_arguments(self, parser):
        parser.add_argument("--alles", action="store_true", help="Ook woningen die al coördinaten hebben opnieuw opzoeken.")

    def handle(self, *args, **opts):
        qs = Woning.objects.filter(online=True)
        qs = qs if opts["alles"] else te_geocoderen(qs)
        sessie = requests.Session()
        gelukt = mislukt = 0
        for w in qs:
            if geocodeer(w, sessie):
                gelukt += 1
            else:
                mislukt += 1
                self.stdout.write(f"  niet gevonden: {w.adres}, {w.postcode} {w.woonplaats}")
        self.stdout.write(f"{gelukt} woningen op de kaart gezet, {mislukt} niet gevonden.")
