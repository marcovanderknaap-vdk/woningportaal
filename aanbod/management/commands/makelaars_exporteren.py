import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from aanbod.models import Makelaar

from .makelaars_laden import VELDEN, VESTIGING_VELDEN


class Command(BaseCommand):
    help = "Schrijf alle makelaars (met vestigingen) uit de database naar makelaars.json."

    def add_arguments(self, parser):
        parser.add_argument("--bestand", default=str(Path(settings.BASE_DIR) / "makelaars.json"))

    def handle(self, *args, **opts):
        pad = Path(opts["bestand"])
        bestaand = {m["naam"]: m for m in json.loads(pad.read_text(encoding="utf-8"))} if pad.exists() else {}
        data = []
        for m in Makelaar.objects.order_by("pk"):
            item = {"naam": m.naam, **{k: getattr(m, k) for k in VELDEN}}
            item["logo_bestand"] = bestaand.get(m.naam, {}).get("logo_bestand", "")
            item["vestigingen"] = [{k: getattr(v, k) for k in VESTIGING_VELDEN} for v in m.vestigingen.all()]
            data.append(item)
        pad.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        self.stdout.write(f"{len(data)} makelaars geschreven naar {pad}")
