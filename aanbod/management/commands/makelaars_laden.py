import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from aanbod.models import Makelaar

VELDEN = ["straat", "postcode", "plaats", "telefoon", "email", "website", "aanbod_url",
          "bron_type", "link_patroon", "extra_urls", "actief"]


class Command(BaseCommand):
    help = "Lees makelaars uit makelaars.json (nieuwe toevoegen, bestaande bijwerken)."

    def add_arguments(self, parser):
        parser.add_argument("--bestand", default=str(Path(settings.BASE_DIR) / "makelaars.json"))
        parser.add_argument("--niet-bijwerken", action="store_true", help="Bestaande makelaars ongemoeid laten.")

    def handle(self, *args, **opts):
        data = json.loads(Path(opts["bestand"]).read_text(encoding="utf-8"))
        for item in data:
            waarden = {k: item[k] for k in VELDEN if k in item}
            m = Makelaar.objects.filter(naam=item["naam"]).first()
            if m is None:
                Makelaar.objects.create(naam=item["naam"], **waarden)
                self.stdout.write(f"+ {item['naam']}")
            elif not opts["niet_bijwerken"]:
                gewijzigd = [k for k, v in waarden.items() if getattr(m, k) != v]
                for k in gewijzigd:
                    setattr(m, k, waarden[k])
                if gewijzigd:
                    m.save()
                    self.stdout.write(f"~ {m.naam}: {', '.join(gewijzigd)}")
