import re
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone


class Makelaar(models.Model):
    class BronType(models.TextChoices):
        AANBODPAGINA = "aanbodpagina", "Aanbodpagina('s) doorlopen"
        SITEMAP = "sitemap", "XML-sitemap"

    naam = models.CharField("bedrijfsnaam", max_length=200)
    email = models.EmailField("e-mail", blank=True)
    website = models.URLField(blank=True)
    aanbod_url = models.URLField(
        "URL naar het aanbod",
        max_length=500,
        help_text="De pagina met het koopaanbod, of een XML-sitemap met alle woningen.",
    )
    bron_type = models.CharField(
        "manier van ophalen",
        max_length=20,
        choices=BronType.choices,
        default=BronType.AANBODPAGINA,
        help_text="Bij een URL die eindigt op .xml wordt automatisch de sitemap gebruikt.",
    )
    link_patroon = models.CharField(
        "patroon voor woninglinks",
        max_length=300,
        blank=True,
        help_text=(
            "Optioneel. Reguliere expressie waaraan een link naar een woning moet voldoen, "
            "bijv. <code>/aanbod/woningaanbod/[^/]+/koop/</code>. Leeg = automatisch bepalen."
        ),
    )
    extra_urls = models.TextField(
        "extra aanbod-URL's",
        blank=True,
        help_text="Optioneel. Extra pagina's of sitemaps (één per regel), bijv. een aparte pagina met verkocht aanbod.",
    )
    max_paginas = models.PositiveIntegerField(
        "maximaal aantal overzichtspagina's", default=30
    )
    actief = models.BooleanField(default=True, help_text="Alleen actieve makelaars worden dagelijks gecontroleerd.")
    logo = models.FileField(
        upload_to="makelaars/", blank=True,
        help_text="SVG, PNG of JPG. Leeg = wordt automatisch van de website van de makelaar gehaald.",
    )
    logo_bron_url = models.URLField(max_length=500, blank=True, editable=False)

    laatste_controle = models.DateTimeField(null=True, blank=True, editable=False)
    laatste_succes = models.DateTimeField(null=True, blank=True, editable=False)
    laatste_fout = models.TextField(blank=True, editable=False)
    aangemaakt = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "makelaar"
        verbose_name_plural = "makelaars"
        ordering = ["naam"]

    def __str__(self):
        return self.naam

    @property
    def effectief_bron_type(self):
        if self.aanbod_url.lower().split("?")[0].endswith(".xml"):
            return self.BronType.SITEMAP
        return self.bron_type

    def alle_aanbod_urls(self):
        urls = [self.aanbod_url]
        urls += [u.strip() for u in self.extra_urls.splitlines() if u.strip()]
        return urls


class Vestiging(models.Model):
    """Een kantoor van een makelaar (adres en telefoon voor bezoekers)."""

    makelaar = models.ForeignKey(Makelaar, on_delete=models.CASCADE, related_name="vestigingen")
    naam = models.CharField("naam", max_length=100, blank=True, help_text="Bijv. 'Kantoor Goes'. Leeg = de plaatsnaam.")
    straat = models.CharField("straat en huisnummer", max_length=200)
    postcode = models.CharField(max_length=10)
    plaats = models.CharField(max_length=100)
    telefoon = models.CharField(max_length=30, blank=True)
    email = models.EmailField("e-mail", blank=True)
    volgorde = models.PositiveSmallIntegerField(default=0)
    lat = models.FloatField(null=True, blank=True, editable=False)
    lon = models.FloatField(null=True, blank=True, editable=False)

    class Meta:
        verbose_name = "vestiging"
        verbose_name_plural = "vestigingen"
        ordering = ["volgorde", "plaats"]

    def __str__(self):
        return f"{self.makelaar} – {self.naam or self.plaats}"

    @property
    def telefoon_link(self):
        """'0118-729 999' → 'tel:+31118729999' (internationaal, werkt ook vanaf een Belgisch toestel)."""
        cijfers = re.sub(r"\D", "", self.telefoon)
        if cijfers.startswith("0031"):
            cijfers = cijfers[4:]
        elif cijfers.startswith("31") and len(cijfers) == 11:
            cijfers = cijfers[2:]
        if cijfers.startswith("0"):
            cijfers = cijfers[1:]
        return f"tel:+31{cijfers}" if cijfers else ""


class WoningQuerySet(models.QuerySet):
    def zichtbaar(self):
        grens = timezone.now() - timedelta(days=settings.VERKOCHT_ZICHTBAAR_DAGEN)
        return (
            self.filter(online=True, verborgen=False, makelaar__actief=True)
            .exclude(status=Woning.Status.VERKOCHT, status_gewijzigd__lt=grens)
        )


class Woning(models.Model):
    class Status(models.TextChoices):
        BESCHIKBAAR = "beschikbaar", "Beschikbaar"
        ONDER_OPTIE = "onder_optie", "Onder optie"
        VERKOCHT_OV = "verkocht_ov", "Verkocht onder voorbehoud"
        VERKOCHT = "verkocht", "Verkocht"

    class Type(models.TextChoices):
        VRIJSTAAND = "vrijstaand", "Vrijstaande woning"
        TWEE_ONDER_EEN_KAP = "2-onder-1-kap", "2-onder-1-kapwoning"
        HOEKWONING = "hoekwoning", "Hoekwoning"
        TUSSENWONING = "tussenwoning", "Tussenwoning"
        APPARTEMENT = "appartement", "Appartement"
        BOUWGROND = "bouwgrond", "Bouwgrond"
        OVERIG = "overig", "Overig"

    makelaar = models.ForeignKey(Makelaar, on_delete=models.CASCADE, related_name="woningen")
    url = models.URLField("URL bij makelaar", max_length=500, unique=True)

    adres = models.CharField(max_length=200, blank=True)
    postcode = models.CharField(max_length=10, blank=True)
    woonplaats = models.CharField(max_length=100, blank=True, db_index=True)

    vraagprijs = models.PositiveIntegerField(null=True, blank=True, db_index=True)
    prijs_tekst = models.CharField("prijs zoals op de site", max_length=120, blank=True)
    prijs_conditie = models.CharField(max_length=20, blank=True, help_text="k.k. of v.o.n.")

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.BESCHIKBAAR, db_index=True)
    status_tekst = models.CharField("status zoals op de site", max_length=100, blank=True)
    woningtype = models.CharField(max_length=20, choices=Type.choices, default=Type.OVERIG, db_index=True)

    woonoppervlakte = models.PositiveIntegerField("woonoppervlakte (m²)", null=True, blank=True)
    perceeloppervlakte = models.PositiveIntegerField("perceeloppervlakte (m²)", null=True, blank=True)
    inhoud = models.PositiveIntegerField("inhoud (m³)", null=True, blank=True)
    kamers = models.PositiveSmallIntegerField(null=True, blank=True)
    slaapkamers = models.PositiveSmallIntegerField(null=True, blank=True)
    bouwjaar = models.PositiveSmallIntegerField(null=True, blank=True)
    energielabel = models.CharField(max_length=10, blank=True)
    omschrijving = models.TextField("korte omschrijving", blank=True)
    kenmerken = models.JSONField(
        "alle kenmerken", default=dict, blank=True,
        help_text="Alle label/waarde-paren die op de detailpagina gevonden zijn.",
    )

    lat = models.FloatField("breedtegraad", null=True, blank=True)
    lon = models.FloatField("lengtegraad", null=True, blank=True)
    geo_gecontroleerd = models.DateTimeField(
        "locatie opgezocht", null=True, blank=True,
        help_text="Wanneer de coördinaten voor het laatst bij PDOK zijn opgezocht.",
    )

    vestiging = models.ForeignKey(
        "Vestiging", null=True, blank=True, on_delete=models.SET_NULL, related_name="woningen",
        help_text="Het kantoor dat de woning aanbiedt.",
    )
    vestiging_bron = models.CharField(
        "hoe het kantoor is bepaald", max_length=20, blank=True,
        choices=[("pagina", "Vermeld op de pagina van de makelaar"), ("afstand", "Dichtstbijzijnde kantoor"),
                 ("enige", "Enige kantoor")],
    )

    foto = models.ImageField("hoofdfoto", upload_to="woningen/%Y/%m/", blank=True)
    foto_bron_url = models.URLField(max_length=1000, blank=True)

    eerst_gezien = models.DateTimeField(default=timezone.now, db_index=True)
    laatst_gezien = models.DateTimeField(default=timezone.now)
    laatst_gecontroleerd = models.DateTimeField(null=True, blank=True)
    status_gewijzigd = models.DateTimeField(default=timezone.now)
    eerste_import = models.BooleanField(
        default=False,
        help_text="Gevonden bij de allereerste controle van deze makelaar; krijgt geen label 'nieuw'.",
    )
    online = models.BooleanField(
        default=True, help_text="Uit = niet meer gevonden op de site van de makelaar."
    )
    verborgen = models.BooleanField(default=False, help_text="Handmatig verbergen op de website.")

    objects = WoningQuerySet.as_manager()

    class Meta:
        verbose_name = "woning"
        verbose_name_plural = "woningen"
        ordering = ["-eerst_gezien"]

    def __str__(self):
        return f"{self.adres}, {self.woonplaats}" if self.adres else self.url

    @property
    def is_nieuw(self):
        if self.eerste_import:
            return False
        return self.eerst_gezien >= timezone.now() - timedelta(days=settings.NIEUW_DAGEN)


class WoningStatusHistorie(models.Model):
    woning = models.ForeignKey(Woning, on_delete=models.CASCADE, related_name="historie")
    datum = models.DateTimeField(default=timezone.now)
    oude_status = models.CharField(max_length=20, blank=True)
    nieuwe_status = models.CharField(max_length=20)
    oude_prijs = models.PositiveIntegerField(null=True, blank=True)
    nieuwe_prijs = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        verbose_name = "wijziging"
        verbose_name_plural = "wijzigingen"
        ordering = ["-datum"]


class OphaalRun(models.Model):
    """Logboek van één controle van één makelaar."""

    makelaar = models.ForeignKey(Makelaar, on_delete=models.CASCADE, related_name="runs")
    gestart = models.DateTimeField(default=timezone.now)
    klaar = models.DateTimeField(null=True, blank=True)
    gelukt = models.BooleanField(default=False)
    links_gevonden = models.PositiveIntegerField(default=0)
    nieuw = models.PositiveIntegerField(default=0)
    bijgewerkt = models.PositiveIntegerField(default=0)
    status_wijzigingen = models.PositiveIntegerField(default=0)
    offline = models.PositiveIntegerField("niet meer gevonden", default=0)
    fouten = models.PositiveIntegerField(default=0)
    log = models.TextField(blank=True)

    class Meta:
        verbose_name = "controle"
        verbose_name_plural = "controles (logboek)"
        ordering = ["-gestart"]

    def __str__(self):
        return f"{self.makelaar} – {self.gestart:%d-%m-%Y %H:%M}"


class GenegeerdeUrl(models.Model):
    """Links die geen (koop)woning bleken; worden een tijd niet opnieuw bekeken."""

    makelaar = models.ForeignKey(Makelaar, on_delete=models.CASCADE, related_name="genegeerd")
    url = models.URLField(max_length=500)
    reden = models.CharField(max_length=200)
    datum = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "genegeerde link"
        verbose_name_plural = "genegeerde links"
        unique_together = [("makelaar", "url")]

    def __str__(self):
        return self.url
