from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q

from aanbod.models import Makelaar
from aanbod.scraper.runner import controleer_alle, rapport_tekst, verstuur_rapport


class Command(BaseCommand):
    help = "Controleer het aanbod van alle actieve makelaars (dagelijks uitvoeren)."

    def add_arguments(self, parser):
        parser.add_argument("--makelaar", help="Alleen deze makelaar (id of deel van de naam).")
        parser.add_argument("--limiet", type=int, help="Max. aantal nieuwe woningen per makelaar (testen).")
        parser.add_argument("--altijd-mailen", action="store_true", help="Ook een rapport mailen als alles goed ging.")

    def handle(self, *args, **opts):
        makelaars = Makelaar.objects.filter(actief=True)
        if opts["makelaar"]:
            q = opts["makelaar"]
            makelaars = Makelaar.objects.filter(Q(pk=int(q)) if q.isdigit() else Q(naam__icontains=q))
            if not makelaars:
                raise CommandError(f"Geen makelaar gevonden voor '{q}'")
        runs = controleer_alle(list(makelaars), uitvoer=self.stdout.write, limiet=opts["limiet"])
        self.stdout.write("\n" + rapport_tekst(runs))
        if verstuur_rapport(runs, altijd=opts["altijd_mailen"]):
            self.stdout.write("Rapport gemaild.")
        if not runs or any(not r.gelukt for r in runs):
            # Niet-nul exitcode zodat ook GitHub Actions/cron een melding geeft
            raise SystemExit(1)
