import threading

from django.contrib import admin, messages
from django.db import close_old_connections
from django.db.models import Count, Q
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html, format_html_join

from .models import GenegeerdeUrl, Makelaar, OphaalRun, Vestiging, Woning, WoningStatusHistorie


def _op_achtergrond(makelaars, droog):
    """Controle in een aparte thread, zodat het beheerscherm niet blijft hangen."""
    from .scraper.runner import Controle, verstuur_rapport

    def taak():
        close_old_connections()
        try:
            runs = [Controle(m, droog=droog, limiet=3 if droog else None).uitvoeren() for m in makelaars]
            if not droog:
                verstuur_rapport(runs)
        finally:
            close_old_connections()

    threading.Thread(target=taak, daemon=True).start()


class VestigingInline(admin.TabularInline):
    model = Vestiging
    extra = 1
    fields = ("naam", "straat", "postcode", "plaats", "telefoon", "email", "volgorde")


@admin.register(Makelaar)
class MakelaarAdmin(admin.ModelAdmin):
    inlines = [VestigingInline]
    list_display = ("naam", "kantoren", "actief", "aantal_woningen", "laatste_controle", "toestand")
    list_filter = ("actief",)
    search_fields = ("naam", "vestigingen__plaats")
    actions = ["nu_controleren", "testen"]
    readonly_fields = ("laatste_controle", "laatste_succes", "laatste_fout_tekst", "recente_controles")
    fieldsets = (
        ("Bedrijfsgegevens", {"fields": ("naam", "email", "website", "logo")}),
        ("Aanbod ophalen", {"fields": ("aanbod_url", "bron_type", "actief")}),
        ("Geavanceerd (meestal niet nodig)", {"classes": ("collapse",), "fields": ("link_patroon", "extra_urls", "max_paginas")}),
        ("Laatste controles", {"fields": ("laatste_controle", "laatste_succes", "laatste_fout_tekst", "recente_controles")}),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            _aantal=Count("woningen", filter=Q(woningen__online=True))
        )

    @admin.display(description="vestigingen")
    def kantoren(self, obj):
        return ", ".join(v.plaats for v in obj.vestigingen.all()) or "–"

    @admin.display(description="woningen online", ordering="_aantal")
    def aantal_woningen(self, obj):
        url = reverse("admin:aanbod_woning_changelist") + f"?makelaar__id__exact={obj.pk}"
        return format_html('<a href="{}">{}</a>', url, obj._aantal)

    @admin.display(description="toestand")
    def toestand(self, obj):
        if not obj.laatste_controle:
            return format_html('<span style="color:#777">nog niet gecontroleerd</span>')
        if obj.laatste_fout:
            return format_html('<span style="color:#b42318;font-weight:600">⚠ probleem</span>')
        return format_html('<span style="color:#137333;font-weight:600">✓ in orde</span>')

    @admin.display(description="laatste foutmelding")
    def laatste_fout_tekst(self, obj):
        return format_html("<pre style='white-space:pre-wrap'>{}</pre>", obj.laatste_fout or "–")

    @admin.display(description="recente controles")
    def recente_controles(self, obj):
        runs = obj.runs.all()[:8]
        if not runs:
            return "–"
        return format_html(
            "<table><tr><th>Datum</th><th>Resultaat</th><th>Links</th><th>Nieuw</th><th>Gewijzigd</th><th>Fouten</th><th></th></tr>{}</table>",
            format_html_join(
                "", "<tr><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td><a href='{}'>log</a></td></tr>",
                (
                    (
                        timezone.localtime(r.gestart).strftime("%d-%m-%Y %H:%M"),
                        ("TEST " if r.log.startswith("TEST") else "") + ("✓" if r.gelukt else "⚠"),
                        r.links_gevonden, r.nieuw, r.status_wijzigingen, r.fouten,
                        reverse("admin:aanbod_ophaalrun_change", args=[r.pk]),
                    )
                    for r in runs
                ),
            ),
        )

    @admin.action(description="Nu controleren (aanbod ophalen en bijwerken)")
    def nu_controleren(self, request, queryset):
        _op_achtergrond(list(queryset), droog=False)
        self.message_user(
            request,
            f"Controle gestart voor {queryset.count()} makelaar(s). Dit kan enkele minuten duren; "
            "het resultaat verschijnt onder 'Controles (logboek)'.",
            messages.SUCCESS,
        )

    @admin.action(description="Testen: kijk of het ophalen werkt (er wordt niets opgeslagen)")
    def testen(self, request, queryset):
        _op_achtergrond(list(queryset), droog=True)
        self.message_user(
            request,
            "Test gestart. Er worden woninglinks gezocht en maximaal 3 nieuwe woningen gelezen. "
            "Bekijk over een paar minuten het resultaat onder 'Controles (logboek)'.",
            messages.SUCCESS,
        )


class HistorieInline(admin.TabularInline):
    model = WoningStatusHistorie
    extra = 0
    can_delete = False
    readonly_fields = ("datum", "oude_status", "nieuwe_status", "oude_prijs", "nieuwe_prijs")

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Woning)
class WoningAdmin(admin.ModelAdmin):
    list_display = ("miniatuur", "adres", "woonplaats", "makelaar", "vraagprijs", "status", "woningtype",
                    "eerst_gezien", "nieuw", "online", "verborgen")
    list_display_links = ("miniatuur", "adres")
    list_filter = ("status", "woningtype", "online", "verborgen", "makelaar", "woonplaats")
    list_editable = ("verborgen",)
    search_fields = ("adres", "woonplaats", "postcode", "url")
    date_hierarchy = "eerst_gezien"
    list_per_page = 50
    inlines = [HistorieInline]
    readonly_fields = ("foto_groot", "url_link", "kenmerken_tabel", "eerst_gezien", "laatst_gezien",
                       "laatst_gecontroleerd", "status_gewijzigd", "status_tekst", "foto_bron_url")
    fieldsets = (
        (None, {"fields": ("foto_groot", "makelaar", "url_link", ("adres", "postcode", "woonplaats"))}),
        ("Prijs en status", {"fields": (("vraagprijs", "prijs_conditie"), "prijs_tekst", ("status", "status_tekst"), "woningtype")}),
        ("Objectdetails", {"fields": (("woonoppervlakte", "perceeloppervlakte", "inhoud"), ("kamers", "slaapkamers", "bouwjaar", "energielabel"), "omschrijving", "kenmerken_tabel")}),
        ("Zichtbaarheid", {"fields": ("verborgen", "online", "eerste_import")}),
        ("Tijdlijn", {"fields": ("eerst_gezien", "laatst_gezien", "laatst_gecontroleerd", "status_gewijzigd")}),
        ("Foto", {"classes": ("collapse",), "fields": ("foto", "foto_bron_url")}),
    )

    @admin.display(description="")
    def miniatuur(self, obj):
        if obj.foto:
            return format_html('<img src="{}" style="width:72px;height:48px;object-fit:cover;border-radius:4px">', obj.foto.url)
        return ""

    @admin.display(description="foto")
    def foto_groot(self, obj):
        if obj.foto:
            return format_html('<img src="{}" style="max-width:420px;border-radius:6px">', obj.foto.url)
        return "–"

    @admin.display(description="URL bij makelaar")
    def url_link(self, obj):
        return format_html('<a href="{0}" target="_blank" rel="noopener">{0}</a>', obj.url)

    @admin.display(description="nieuw", boolean=True)
    def nieuw(self, obj):
        return obj.is_nieuw

    @admin.display(description="alle gevonden kenmerken")
    def kenmerken_tabel(self, obj):
        if not obj.kenmerken:
            return "–"
        return format_html(
            "<table>{}</table>",
            format_html_join("", "<tr><th style='text-align:left'>{}</th><td>{}</td></tr>", obj.kenmerken.items()),
        )


@admin.register(OphaalRun)
class OphaalRunAdmin(admin.ModelAdmin):
    list_display = ("gestart", "makelaar", "soort", "gelukt", "links_gevonden", "nieuw", "status_wijzigingen", "offline", "fouten", "duur")
    list_filter = ("gelukt", "makelaar")
    readonly_fields = [f.name for f in OphaalRun._meta.fields if f.name != "log"] + ["log_tekst"]
    exclude = ("log",)

    def has_add_permission(self, request):
        return False

    @admin.display(description="soort")
    def soort(self, obj):
        return "test" if obj.log.startswith("TEST") else "controle"

    @admin.display(description="duur")
    def duur(self, obj):
        if obj.klaar:
            s = int((obj.klaar - obj.gestart).total_seconds())
            return f"{s // 60}m {s % 60:02d}s"
        return "bezig…"

    @admin.display(description="logboek")
    def log_tekst(self, obj):
        return format_html("<pre style='white-space:pre-wrap;max-width:1100px'>{}</pre>", obj.log)


@admin.register(GenegeerdeUrl)
class GenegeerdeUrlAdmin(admin.ModelAdmin):
    list_display = ("url", "makelaar", "reden", "datum")
    list_filter = ("makelaar", "reden")
    search_fields = ("url",)
