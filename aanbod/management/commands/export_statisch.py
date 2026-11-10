"""Exporteer de publieke website als statische HTML (voor GitHub Pages e.d.)."""
import shutil
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.test import RequestFactory

from aanbod import views
from aanbod.models import Woning


class Command(BaseCommand):
    help = "Schrijf de publieke site als statische bestanden naar een map."

    def add_arguments(self, parser):
        parser.add_argument("--uit", default="site", help="Doelmap (wordt leeggemaakt).")
        parser.add_argument("--basis", default="/", help="Basispad van de site, bijv. /woningportaal/")

    def handle(self, *args, **opts):
        uit = Path(opts["uit"])
        basis = "/" + opts["basis"].strip("/") + "/" if opts["basis"].strip("/") else "/"
        if uit.exists():
            shutil.rmtree(uit)
        uit.mkdir(parents=True)
        rf = RequestFactory()

        def schrijf(pad, view, *args):
            request = rf.get(basis + pad)
            request.basis_url = basis
            request.statisch = True
            response = view(request, *args)
            doel = uit / pad / "index.html"
            doel.parent.mkdir(parents=True, exist_ok=True)
            doel.write_bytes(response.content)

        schrijf("", views.index)
        schrijf("makelaars/", views.makelaars)
        woningen = list(Woning.objects.zichtbaar())
        for w in woningen:
            schrijf(f"woning/{w.pk}/", views.detail, w.pk)
            if w.foto and Path(w.foto.path).exists():
                doel = uit / settings.MEDIA_URL.strip("/") / w.foto.name
                doel.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(w.foto.path, doel)

        from aanbod.models import Makelaar
        for m in Makelaar.objects.exclude(logo=""):
            if Path(m.logo.path).exists():
                doel = uit / settings.MEDIA_URL.strip("/") / m.logo.name
                doel.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(m.logo.path, doel)

        statisch = Path(settings.BASE_DIR) / "aanbod" / "static"
        shutil.copytree(statisch, uit / "static")
        (uit / ".nojekyll").write_text("")
        request = rf.get("/robots.txt")
        (uit / "robots.txt").write_bytes(views.robots_txt(request).content)
        (uit / "404.html").write_text(
            f'<!doctype html><meta charset="utf-8"><title>Niet gevonden</title>'
            f'<p>Deze woning staat niet (meer) in het overzicht. <a href="{basis}">Naar het aanbod</a></p>'
        )
        self.stdout.write(f"{len(woningen)} woningen geëxporteerd naar {uit}/ (basis {basis})")
