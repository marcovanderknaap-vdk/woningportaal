from django.core.management.base import BaseCommand
from django.db.models import Count, Q

from aanbod.models import Woning
from aanbod.scraper.detail import parse_detail
from aanbod.scraper.http import Fetcher
from aanbod.scraper.vestiging import koppel


class Command(BaseCommand):
    help = "Bepaal per woning het aanbiedende kantoor (dit gebeurt ook bij de dagelijkse controle)."

    def add_arguments(self, parser):
        parser.add_argument("--zonder-ophalen", action="store_true",
                            help="Pagina's niet ophalen; alleen het dichtstbijzijnde kantoor bepalen waar nog niets bekend is.")
        parser.add_argument("--makelaar", help="Alleen deze makelaar (deel van de naam).")
        parser.add_argument("--limiet", type=int, help="Max. aantal woningen per makelaar (testen).")

    def handle(self, *args, **opts):
        qs = Woning.objects.filter(online=True).select_related("makelaar")
        if opts["makelaar"]:
            qs = qs.filter(makelaar__naam__icontains=opts["makelaar"])
        if opts["zonder_ophalen"]:
            n = sum(koppel(w) for w in qs.filter(Q(vestiging__isnull=True) | Q(vestiging_bron="")))
            self.stdout.write(f"{n} woningen gekoppeld aan een kantoor (zonder ophalen).")
            return
        # Pagina's alleen ophalen bij makelaars met meer dan één kantoor
        qs = qs.annotate(n_kantoren=Count("makelaar__vestigingen")).filter(n_kantoren__gt=1)
        fetcher, per_makelaar, telling = Fetcher(), {}, {"pagina": 0, "afstand": 0}
        for w in qs.order_by("makelaar", "pk"):
            if opts["limiet"] and per_makelaar.get(w.makelaar_id, 0) >= opts["limiet"]:
                continue
            per_makelaar[w.makelaar_id] = per_makelaar.get(w.makelaar_id, 0) + 1
            r = fetcher.get(w.url)
            cijfers = parse_detail(r.text, r.url).paginacijfers if r.status_code == 200 else None
            koppel(w, cijfers)
            telling[w.vestiging_bron] = telling.get(w.vestiging_bron, 0) + 1
            self.stdout.write(f"  {w.makelaar.naam}: {w.adres}, {w.woonplaats} → {w.vestiging and w.vestiging.plaats} ({w.vestiging_bron})")
        self.stdout.write(f"Klaar: {telling}")
