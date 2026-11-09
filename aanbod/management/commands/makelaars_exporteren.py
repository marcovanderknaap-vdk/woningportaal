import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from aanbod.models import Makelaar

from .makelaars_laden import VELDEN


class Command(BaseCommand):
    help = "Schrijf alle makelaars uit de database naar makelaars.json."

    def add_arguments(self, parser):
        parser.add_argument("--bestand", default=str(Path(settings.BASE_DIR) / "makelaars.json"))

    def handle(self, *args, **opts):
        data = [{"naam": m.naam, **{k: getattr(m, k) for k in VELDEN}} for m in Makelaar.objects.order_by("pk")]
        Path(opts["bestand"]).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        self.stdout.write(f"{len(data)} makelaars geschreven naar {opts['bestand']}")
