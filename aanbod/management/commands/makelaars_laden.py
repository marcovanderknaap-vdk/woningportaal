import hashlib
import json
from pathlib import Path

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand

from aanbod.models import Makelaar, Vestiging

VELDEN = ["email", "website", "aanbod_url", "bron_type", "link_patroon", "extra_urls", "actief"]
VESTIGING_VELDEN = ["naam", "straat", "postcode", "plaats", "telefoon", "email"]


class Command(BaseCommand):
    help = "Lees makelaars, vestigingen en vaste logo's uit makelaars.json (nieuwe toevoegen, bestaande bijwerken)."

    def add_arguments(self, parser):
        parser.add_argument("--bestand", default=str(Path(settings.BASE_DIR) / "makelaars.json"))
        parser.add_argument("--niet-bijwerken", action="store_true", help="Bestaande makelaars ongemoeid laten.")

    def handle(self, *args, **opts):
        data = json.loads(Path(opts["bestand"]).read_text(encoding="utf-8"))
        for item in data:
            waarden = {k: item[k] for k in VELDEN if k in item}
            m = Makelaar.objects.filter(naam=item["naam"]).first()
            if m is None:
                m = Makelaar.objects.create(naam=item["naam"], **waarden)
                self.stdout.write(f"+ {item['naam']}")
            elif opts["niet_bijwerken"]:
                continue
            else:
                gewijzigd = [k for k, v in waarden.items() if getattr(m, k) != v]
                for k in gewijzigd:
                    setattr(m, k, waarden[k])
                if gewijzigd:
                    m.save()
                    self.stdout.write(f"~ {m.naam}: {', '.join(gewijzigd)}")
            if "vestigingen" in item:
                self._vestigingen(m, item["vestigingen"])
            if item.get("logo_bestand"):
                self._logo(m, Path(settings.BASE_DIR) / item["logo_bestand"])

    def _vestigingen(self, m, lijst):
        gewenst = [{k: v.get(k, "") for k in VESTIGING_VELDEN} for v in lijst]
        huidig = [{k: getattr(v, k) for k in VESTIGING_VELDEN} for v in m.vestigingen.order_by("volgorde", "pk")]
        if gewenst == huidig:
            return
        m.vestigingen.all().delete()
        for i, v in enumerate(gewenst):
            Vestiging.objects.create(makelaar=m, volgorde=i, **v)
        self.stdout.write(f"~ {m.naam}: {len(gewenst)} vestiging(en)")

    def _logo(self, m, pad):
        """Vast logo uit de repository; gaat vóór het automatisch opgehaalde logo."""
        inhoud = pad.read_bytes()
        kenmerk = "bestand:" + hashlib.sha1(inhoud).hexdigest()[:12]
        if m.logo and m.logo_bron_url == kenmerk:
            return
        if m.logo:
            m.logo.delete(save=False)
        m.logo.save(f"makelaar-{m.pk}{pad.suffix}", ContentFile(inhoud), save=False)
        m.logo_bron_url = kenmerk
        m.save(update_fields=["logo", "logo_bron_url"])
        self.stdout.write(f"~ {m.naam}: logo uit {pad.name}")
