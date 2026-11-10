from django.core.management.base import BaseCommand
from django.db.models import Count

from aanbod.models import Woning


class Command(BaseCommand):
    help = "Voeg woningen met hetzelfde adres bij dezelfde makelaar samen (bijv. na het opnieuw in verkoop zetten)."

    def handle(self, *args, **opts):
        groepen = (
            Woning.objects.exclude(adres="").values("makelaar", "adres", "woonplaats")
            .annotate(n=Count("id")).filter(n__gt=1)
        )
        for g in groepen:
            lijst = list(Woning.objects.filter(makelaar=g["makelaar"], adres=g["adres"], woonplaats=g["woonplaats"]).order_by("eerst_gezien"))
            oudste, nieuwste = lijst[0], max(lijst, key=lambda w: w.laatst_gecontroleerd or w.eerst_gezien)
            # De oudste blijft bestaan (datum van eerste opname), met de gegevens en link van de meest recente
            for veld in ("url", "vraagprijs", "prijs_tekst", "prijs_conditie", "status", "status_tekst", "status_gewijzigd",
                         "omschrijving", "kenmerken", "foto_bron_url", "laatst_gezien", "laatst_gecontroleerd", "online"):
                setattr(oudste, veld, getattr(nieuwste, veld))
            if nieuwste.foto and nieuwste is not oudste:
                if oudste.foto:
                    oudste.foto.delete(save=False)
                oudste.foto = nieuwste.foto
            for w in lijst[1:]:
                w.historie.update(woning=oudste)
                if w.foto == oudste.foto:
                    w.foto = ""
                w.delete()
            oudste.save()
            self.stdout.write(f"Samengevoegd: {oudste} ({len(lijst)} → 1)")
