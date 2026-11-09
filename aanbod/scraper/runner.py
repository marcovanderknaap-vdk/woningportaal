"""De dagelijkse controle: nieuw aanbod ophalen en bestaand aanbod bijwerken."""
import io
import logging
import traceback
from datetime import timedelta
from urllib.parse import urlsplit

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.mail import send_mail
from django.db.models import Q
from django.utils import timezone
from PIL import Image

from ..models import GenegeerdeUrl, Makelaar, OphaalRun, Woning, WoningStatusHistorie
from .detail import parse_detail
from .discovery import vind_woninglinks
from .http import Fetcher, NietToegestaan

log = logging.getLogger("aanbod.scraper")

GENEGEERD_GELDIG_DAGEN = 30


class Controle:
    def __init__(self, makelaar, fetcher=None, droog=False, limiet=None, uitvoer=None):
        self.m = makelaar
        self.fetcher = fetcher or Fetcher()
        self.droog = droog  # alleen tonen, niets opslaan
        self.limiet = limiet  # max. aantal nieuwe woningen (handig bij testen)
        self.uitvoer = uitvoer
        self.regels = []
        self.run = None

    def _log(self, tekst):
        self.regels.append(tekst)
        if self.uitvoer:
            self.uitvoer(f"  {tekst}")
        else:
            log.info("[%s] %s", self.m.naam, tekst)

    # ------------------------------------------------------------------
    def uitvoeren(self):
        nu = timezone.now()
        run = OphaalRun(makelaar=self.m, gestart=nu)
        self.run = run
        if self.droog:
            self._log("TESTRUN – er wordt niets opgeslagen, alleen gekeken of het ophalen werkt.")
        run.save()
        try:
            self._uitvoeren(run)
            run.gelukt = run.links_gevonden > 0 and run.fouten <= max(3, run.links_gevonden // 5)
            if run.links_gevonden == 0:
                self._log("FOUT: geen enkele woninglink gevonden – is de site of de aanbod-URL gewijzigd?")
        except Exception as exc:  # noqa: BLE001 – één makelaar mag de rest niet stoppen
            run.gelukt = False
            run.fouten += 1
            self._log(f"FOUT: {exc}")
            self._log(traceback.format_exc(limit=3))
        run.klaar = timezone.now()
        run.log = "\n".join(self.regels)
        run.save()
        if not self.droog:
            self.m.laatste_controle = run.klaar
            if run.gelukt:
                self.m.laatste_succes = run.klaar
                self.m.laatste_fout = ""
            else:
                self.m.laatste_fout = "\n".join(r for r in self.regels if "FOUT" in r)[:2000] or "Controle mislukt"
            self.m.save(update_fields=["laatste_controle", "laatste_succes", "laatste_fout"])
        return run

    def _uitvoeren(self, run):
        eerste_import = not self.m.woningen.exists() and self.m.laatste_succes is None
        links = vind_woninglinks(self.fetcher, self.m, self.regels)
        run.links_gevonden = len(links)
        if not links:
            return

        bekend = set(self.m.woningen.values_list("url", flat=True))
        grens = timezone.now() - timedelta(days=GENEGEERD_GELDIG_DAGEN)
        genegeerd = set(self.m.genegeerd.filter(datum__gte=grens).values_list("url", flat=True))
        nieuw = [l for l in links if l not in bekend and l not in genegeerd]
        if self.limiet is not None:
            nieuw = nieuw[: self.limiet]
        self._log(f"{len(nieuw)} nieuwe link(s) te bekijken, {len(bekend)} bekende woning(en)")

        for url in nieuw:
            self._verwerk_nieuw(url, eerste_import, run)

        # Bestaand aanbod: status/prijs controleren via de detailpagina
        controle_grens = timezone.now() - timedelta(days=settings.VERKOCHT_CONTROLE_DAGEN)
        te_controleren = self.m.woningen.exclude(
            Q(status=Woning.Status.VERKOCHT, status_gewijzigd__lt=controle_grens)
            | Q(online=False, laatst_gezien__lt=controle_grens)
        ).exclude(url__in=nieuw)
        if self.droog:
            te_controleren = te_controleren.none()
        gevonden = set(links)
        for woning in te_controleren:
            self._controleer_bestaand(woning, woning.url in gevonden, run)

    # ------------------------------------------------------------------
    def _haal(self, url):
        r = self.fetcher.get(url)
        if r.status_code in (404, 410):
            return None, "weg"
        if r.status_code != 200:
            raise RuntimeError(f"HTTP {r.status_code} voor {url}")
        res = parse_detail(r.text, r.url)
        res.url = url
        # Doorgestuurd naar een andere pagina (bijv. het overzicht) = woning weg
        if urlsplit(r.url).path.rstrip("/") != urlsplit(url).path.rstrip("/") and not res.bruikbaar:
            return None, "weg"
        return res, None

    def _negeer(self, url, reden):
        self._log(f"overgeslagen ({reden}): {url}")
        if not self.droog:
            GenegeerdeUrl.objects.update_or_create(
                makelaar=self.m, url=url, defaults={"reden": reden, "datum": timezone.now()}
            )

    def _verwerk_nieuw(self, url, eerste_import, run):
        try:
            res, fout = self._haal(url)
        except NietToegestaan:
            self._negeer(url, "robots.txt staat ophalen niet toe")
            return
        except Exception as exc:  # noqa: BLE001
            run.fouten += 1
            self._log(f"FOUT bij {url}: {exc}")
            return
        if res is None:
            self._negeer(url, "pagina bestaat niet (meer)")
            return
        if res.is_huur:
            return self._negeer(url, "huurwoning")
        if res.geen_woning:
            return self._negeer(url, "geen woning (garage, bedrijfsruimte e.d.)")
        if res.status == "verkocht":
            return self._negeer(url, "al verkocht bij eerste vondst")
        if res.status in ("verhuurd", "ingetrokken"):
            return self._negeer(url, res.status)
        if not res.bruikbaar:
            run.fouten += 1
            self._log(f"FOUT: kon geen adres/prijs/status lezen op {url}")
            return

        self._log(f"NIEUW: {res.adres}, {res.woonplaats} – {res.prijs_tekst or 'prijs onbekend'} ({res.status})")
        run.nieuw += 1
        if self.droog:
            return
        nu = timezone.now()
        woning = Woning(makelaar=self.m, url=url, eerst_gezien=nu, laatst_gezien=nu,
                        laatst_gecontroleerd=nu, status_gewijzigd=nu, eerste_import=eerste_import)
        self._vul(woning, res)
        woning.save()
        self._foto(woning, res.foto_url)
        WoningStatusHistorie.objects.create(woning=woning, nieuwe_status=woning.status, nieuwe_prijs=woning.vraagprijs)

    def _controleer_bestaand(self, woning, in_overzicht, run):
        nu = timezone.now()
        try:
            res, fout = self._haal(woning.url)
        except NietToegestaan:
            return
        except Exception as exc:  # noqa: BLE001
            run.fouten += 1
            self._log(f"FOUT bij controle {woning}: {exc}")
            return
        woning.laatst_gecontroleerd = nu
        if res is None:
            if woning.online:
                self._log(f"NIET MEER ONLINE: {woning}")
                woning.online = False
                run.offline += 1
            woning.save(update_fields=["online", "laatst_gecontroleerd"])
            return
        if res.is_huur or res.geen_woning:
            if woning.online:
                self._log(f"GEEN KOOPWONING (meer), offline gezet: {woning}")
                run.offline += 1
            woning.online = False
            woning.save(update_fields=["online", "laatst_gecontroleerd"])
            return
        if not woning.online:
            self._log(f"WEER ONLINE: {woning}")
        woning.online = True
        woning.laatst_gezien = nu

        oude_status, oude_prijs = woning.status, woning.vraagprijs
        if res.status is None and res.vraagprijs is None:
            run.fouten += 1
            self._log(f"FOUT: kon status/prijs niet meer lezen voor {woning} – sitewijziging?")
            woning.save(update_fields=["online", "laatst_gezien", "laatst_gecontroleerd"])
            return
        self._vul(woning, res, bestaand=True)
        if woning.status != oude_status or woning.vraagprijs != oude_prijs:
            if woning.status != oude_status:
                woning.status_gewijzigd = nu
                run.status_wijzigingen += 1
            self._log(
                f"GEWIJZIGD: {woning}: {oude_status} → {woning.status}, "
                f"prijs {oude_prijs} → {woning.vraagprijs}"
            )
            WoningStatusHistorie.objects.create(
                woning=woning, oude_status=oude_status, nieuwe_status=woning.status,
                oude_prijs=oude_prijs, nieuwe_prijs=woning.vraagprijs,
            )
        run.bijgewerkt += 1
        woning.save()
        if not woning.foto and res.foto_url:
            self._foto(woning, res.foto_url)

    def _vul(self, woning, res, bestaand=False):
        # Status: verhuurd/ingetrokken zijn geen statussen op het portaal
        if res.status in dict(Woning.Status.choices):
            woning.status = res.status
        elif res.status == "ingetrokken":
            woning.online = False
        woning.status_tekst = res.status_tekst[:100]
        if res.vraagprijs is not None or not bestaand:
            woning.vraagprijs = res.vraagprijs
            woning.prijs_tekst = res.prijs_tekst[:120]
            woning.prijs_conditie = res.prijs_conditie
        # Handmatig aangepaste adresgegevens niet overschrijven
        if not bestaand or not woning.adres:
            woning.adres = res.adres[:200]
            woning.postcode = res.postcode[:10]
        if not bestaand or not woning.woonplaats:
            woning.woonplaats = res.woonplaats[:100]
        woning.woningtype = res.woningtype
        for veld in ("woonoppervlakte", "perceeloppervlakte", "inhoud", "kamers", "slaapkamers", "bouwjaar"):
            waarde = getattr(res, veld)
            if waarde is not None:
                setattr(woning, veld, waarde)
        woning.energielabel = res.energielabel or woning.energielabel
        woning.omschrijving = res.omschrijving or woning.omschrijving
        woning.kenmerken = res.kenmerken or woning.kenmerken
        if res.foto_url:
            woning.foto_bron_url = res.foto_url

    def _foto(self, woning, url):
        if not url:
            return
        try:
            r = self.fetcher.get(url, check_robots=False, binary=True)
            if r.status_code != 200:
                raise RuntimeError(f"HTTP {r.status_code}")
            img = Image.open(io.BytesIO(r.content))
            img = img.convert("RGB")
            if img.width > settings.FOTO_MAX_BREEDTE:
                hoogte = round(img.height * settings.FOTO_MAX_BREEDTE / img.width)
                img = img.resize((settings.FOTO_MAX_BREEDTE, hoogte), Image.LANCZOS)
            buf = io.BytesIO()
            img.save(buf, "JPEG", quality=82, optimize=True, progressive=True)
            woning.foto.save(f"woning-{woning.pk}.jpg", ContentFile(buf.getvalue()), save=True)
        except Exception as exc:  # noqa: BLE001 – foto is niet kritisch
            self._log(f"Foto kon niet worden opgehaald voor {woning}: {exc}")


# ----------------------------------------------------------------------
def controleer_alle(makelaars=None, uitvoer=None, limiet=None):
    makelaars = makelaars if makelaars is not None else Makelaar.objects.filter(actief=True)
    fetcher = Fetcher()
    runs = []
    for m in makelaars:
        if uitvoer:
            uitvoer(f"== {m.naam}")
        runs.append(Controle(m, fetcher=fetcher, limiet=limiet, uitvoer=uitvoer).uitvoeren())
    return runs


def rapport_tekst(runs):
    regels = []
    for run in runs:
        status = "OK" if run.gelukt else "PROBLEEM"
        regels.append(
            f"{status:9} {run.makelaar.naam}: {run.links_gevonden} links, {run.nieuw} nieuw, "
            f"{run.status_wijzigingen} statuswijzigingen, {run.offline} offline, {run.fouten} fouten"
        )
    problemen = [r for r in runs if not r.gelukt or r.fouten]
    if problemen:
        regels.append("\nDetails van makelaars met problemen:\n")
        for run in problemen:
            regels.append(f"--- {run.makelaar.naam} ({run.makelaar.aanbod_url})")
            regels.extend(r for r in run.log.splitlines() if "FOUT" in r or "HTTP" in r)
            regels.append("")
    return "\n".join(regels)


def verstuur_rapport(runs, altijd=False):
    problemen = [r for r in runs if not r.gelukt or r.fouten]
    if not settings.RAPPORT_EMAIL or not (problemen or altijd):
        return False
    onderwerp = (
        f"[{settings.PORTAAL_NAAM}] Storing bij {len(problemen)} makelaar(s)"
        if problemen
        else f"[{settings.PORTAAL_NAAM}] Dagelijkse controle geslaagd"
    )
    send_mail(onderwerp, rapport_tekst(runs), settings.DEFAULT_FROM_EMAIL, settings.RAPPORT_EMAIL)
    return True
