"""Opslag beperken: foto's en archiefregels van verkochte of verdwenen woningen opruimen.

- Een woning is 'afgerond' als hij verkocht is of niet meer op de site van de makelaar staat.
  Het moment telt vanaf de statuswijziging naar verkocht, of vanaf de laatste keer dat hij gezien is.
- Na FOTO_BEWAREN_DAGEN: foto verwijderen; de woning blijft als archiefregel (adres, prijzen,
  statushistorie, kenmerken) bewaard, bijv. om een woning te herkennen die opnieuw in verkoop komt.
- Na ARCHIEF_BEWAREN_DAGEN: archiefregel verwijderen.
- Daarnaast: oude logboeken, oude genegeerde links en losse fotobestanden zonder woning.
"""
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils import timezone

from aanbod.models import GenegeerdeUrl, Makelaar, OphaalRun, Woning


def afgerond_voor(grens):
    return Woning.objects.filter(
        Q(status=Woning.Status.VERKOCHT, status_gewijzigd__lt=grens) | Q(online=False, laatst_gezien__lt=grens)
    )


class Command(BaseCommand):
    help = "Ruim foto's en archiefregels op van woningen die al lang verkocht of verdwenen zijn."

    def add_arguments(self, parser):
        parser.add_argument("--droog", action="store_true", help="Alleen tonen wat er zou gebeuren.")

    def handle(self, *args, **opts):
        nu, droog = timezone.now(), opts["droog"]
        prefix = "(droog) " if droog else ""

        # 1. Archiefregels verwijderen
        archief = afgerond_voor(nu - timedelta(days=settings.ARCHIEF_BEWAREN_DAGEN))
        n_archief = archief.count()
        if not droog:
            for w in archief:
                if w.foto:
                    w.foto.delete(save=False)
                w.delete()

        # 2. Foto's verwijderen
        fotos = afgerond_voor(nu - timedelta(days=settings.FOTO_BEWAREN_DAGEN)).exclude(foto="")
        n_fotos, bytes_vrij = 0, 0
        for w in fotos:
            try:
                bytes_vrij += w.foto.size
            except (OSError, ValueError):
                pass
            n_fotos += 1
            if not droog:
                w.foto.delete(save=False)
                w.save(update_fields=["foto"])

        # 3. Logboeken en genegeerde links
        n_logs = OphaalRun.objects.filter(gestart__lt=nu - timedelta(days=settings.LOGBOEK_BEWAREN_DAGEN)).count()
        n_gen = GenegeerdeUrl.objects.filter(datum__lt=nu - timedelta(days=settings.GENEGEERD_BEWAREN_DAGEN)).count()
        if not droog:
            OphaalRun.objects.filter(gestart__lt=nu - timedelta(days=settings.LOGBOEK_BEWAREN_DAGEN)).delete()
            GenegeerdeUrl.objects.filter(datum__lt=nu - timedelta(days=settings.GENEGEERD_BEWAREN_DAGEN)).delete()

        # 4. Losse bestanden in de mediamap waar geen woning of makelaar meer naar verwijst.
        #    Veiligheidsrem: alleen bestanden ouder dan een dag, en nooit als het om een groot deel
        #    van alle bestanden gaat (dan klopt er iets niet, bijv. een lege of verkeerde database).
        in_gebruik = {w.foto.name for w in Woning.objects.exclude(foto="").only("foto")}
        in_gebruik |= {m.logo.name for m in Makelaar.objects.exclude(logo="").only("logo")}
        media = Path(settings.MEDIA_ROOT)
        alle = [p for map_ in ("woningen", "makelaars") if (media / map_).exists()
                for p in (media / map_).rglob("*") if p.is_file()]
        drempel = (nu - timedelta(days=1)).timestamp()
        wezen = [p for p in alle if str(p.relative_to(media)) not in in_gebruik and p.stat().st_mtime < drempel]
        n_wees = 0
        if wezen and (not in_gebruik or len(wezen) > max(20, len(alle) // 10)):
            self.stderr.write(
                f"Opruimen van losse bestanden overgeslagen: {len(wezen)} van {len(alle)} bestanden zouden "
                "verwijderd worden. Dat is te veel om te vertrouwen; controleer database en mediamap."
            )
        else:
            for pad in wezen:
                n_wees += 1
                bytes_vrij += pad.stat().st_size
                if not droog:
                    pad.unlink()

        self.stdout.write(
            f"{prefix}{n_fotos} foto's en {n_wees} losse bestanden verwijderd ({bytes_vrij / 1e6:.1f} MB), "
            f"{n_archief} archiefregels, {n_logs} logboeken en {n_gen} genegeerde links opgeruimd."
        )
