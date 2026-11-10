from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from .models import Makelaar, Woning
from .scraper.detail import normaliseer_status, normaliseer_type, parse_adres, parse_detail, parse_prijs
from .scraper.discovery import kies_woninglinks
from .scraper.plaatsen import zoek_plaats


class NormaliseerTest(TestCase):
    def test_prijs(self):
        self.assertEqual(parse_prijs("€ 395.000,- k.k."), (395000, "k.k."))
        self.assertEqual(parse_prijs("Vraagprijs € 1.425.000 kosten koper"), (1425000, "k.k."))
        self.assertEqual(parse_prijs("€ 155.000,- v.o.n."), (155000, "v.o.n."))
        self.assertEqual(parse_prijs("Prijs op aanvraag")[0], None)

    def test_status(self):
        self.assertEqual(normaliseer_status("Verkocht onder voorbehoud"), "verkocht_ov")
        self.assertEqual(normaliseer_status("Onder bod"), "onder_optie")
        self.assertEqual(normaliseer_status("Onder optie"), "onder_optie")
        self.assertEqual(normaliseer_status("Verkocht"), "verkocht")
        self.assertEqual(normaliseer_status("Beschikbaar"), "beschikbaar")

    def test_type(self):
        self.assertEqual(normaliseer_type("Eengezinswoning", "Tussenwoning"), "tussenwoning")
        self.assertEqual(normaliseer_type("Eengezinswoning", "2-onder-1-kapwoning"), "2-onder-1-kap")
        self.assertEqual(normaliseer_type("Villa", "Vrijstaande woning"), "vrijstaand")
        self.assertEqual(normaliseer_type("Bovenwoning"), "appartement")
        self.assertEqual(normaliseer_type("Eengezinswoning", "Halfvrijstaande woning"), "2-onder-1-kap")

    def test_plaats(self):
        self.assertEqual(zoek_plaats("Spanjaardstraat 13 in Middelburg"), "Middelburg")
        self.assertEqual(zoek_plaats("annoijstraat 6 sas van gent"), "Sas van Gent")
        self.assertEqual(zoek_plaats("Meiveld 23 Oost-Souburg"), "Oost-Souburg")
        self.assertEqual(zoek_plaats("Kapellestraat 5 Veere"), "Veere")

    def test_adres_uit_titel(self):
        self.assertEqual(
            parse_adres("Huis te koop: Grootmede 55, 4337 AB Middelburg - M2 Makelaars", "https://x/"),
            ("Grootmede 55", "4337 AB", "Middelburg"),
        )
        self.assertEqual(
            parse_adres("Spanjaardstraat 13 in Middelburg 4331 EN: Woonhuis te koop.", "https://x/"),
            ("Spanjaardstraat 13", "4331 EN", "Middelburg"),
        )
        self.assertEqual(parse_adres("Statenlaan 8 (Middelburg) | Kuub Makelaars", "https://x/")[::2], ("Statenlaan 8", "Middelburg"))


class DetailTest(TestCase):
    HTML = """<html><head><title>Huis te koop: Dorpsstraat 1, 4321 AB Goes - Makelaar</title>
    <meta property="og:image" content="/foto.jpg"></head><body>
    <nav>Verkocht</nav>
    <div class="kenmerken"><span>Vraagprijs</span><span>€ 350.000,- k.k.</span>
    <span>Status</span><span>Verkocht onder voorbehoud</span>
    <span>Soort woning</span><span>Eengezinswoning</span><span>Type woning</span><span>Hoekwoning</span>
    <span>Woonoppervlakte</span><span>120 m<sup>2</sup></span><span>Aantal kamers</span><span>5</span>
    <span>Bouwjaar</span><span>1985</span><span>Energielabel</span><span>B</span></div></body></html>"""

    def test_parse(self):
        r = parse_detail(self.HTML, "https://makelaar.nl/woning/dorpsstraat-1-goes/")
        self.assertEqual((r.adres, r.postcode, r.woonplaats), ("Dorpsstraat 1", "4321 AB", "Goes"))
        self.assertEqual(r.vraagprijs, 350000)
        self.assertEqual(r.status, "verkocht_ov")
        self.assertEqual(r.woningtype, "hoekwoning")
        self.assertEqual((r.woonoppervlakte, r.kamers, r.bouwjaar, r.energielabel), (120, 5, 1985, "B"))
        self.assertEqual(r.foto_url, "https://makelaar.nl/foto.jpg")


class OmschrijvingEnKenmerkenTest(TestCase):
    HTML = """<html><head><title>Statenlaan 8 (Middelburg) | Kuub Makelaars</title>
    <meta property="og:description" content="Kuub Makelaars is dé makelaar in Zeeland met vestigingen in Axel, Goes en Middelburg.">
    </head><body><ul><li>Wonen</li><li>Aanbod</li></ul>
    <h2>Omschrijving</h2><p>Kenmerken</p>
    <p>Ruim en licht appartement met drie slaapkamers, moderne keuken en badkamer, twee balkons en een groene omgeving.</p>
    <p>De Statenlaan is gelegen in een rustige woonwijk op loopafstand van het centrum van Middelburg.</p>
    <div><span>110 m²</span><span>Kamers</span><span>Benieuwd of je de woning kan betalen?</span></div>
    <dl><dt>Vraagprijs</dt><dd>€ 275.000,- k.k.</dd><dt>Aantal kamers</dt><dd>4</dd><dt>Soort woonhuis</dt><dd>Eengezinswoning</dd></dl>
    </body></html>"""

    def test_omschrijving_van_pagina_niet_van_kantoor(self):
        r = parse_detail(self.HTML, "https://www.kuubmakelaars.nl/woning/statenlaan-8-middelburg/")
        self.assertTrue(r.omschrijving.startswith("Ruim en licht appartement"))
        self.assertEqual(r.woningtype, "appartement")

    def test_losse_woorden_geen_kenmerk(self):
        r = parse_detail(self.HTML, "https://www.kuubmakelaars.nl/woning/statenlaan-8-middelburg/")
        self.assertNotIn("Kamers", r.kenmerken)
        self.assertNotIn("Wonen", r.kenmerken)
        self.assertEqual(r.kamers, 4)


class LinksTest(TestCase):
    def test_automatisch(self):
        links = [
            "https://m.nl/aanbod/middelburg-grootmede-55/", "https://m.nl/aanbod/vlissingen-singel-58/",
            "https://m.nl/aanbod/goes-markt-1/", "https://m.nl/aanbod/beschikbaar/page/2/",
            "https://m.nl/nieuws/top-10-tips-2024/", "https://m.nl/contact/", "https://m.nl/?p=12",
        ]
        self.assertEqual(len(kies_woninglinks(links)), 3)


class TelefoonTest(TestCase):
    def test_tel_link(self):
        from .models import Vestiging
        m = Makelaar.objects.create(naam="T", aanbod_url="https://t.nl/")
        for invoer, verwacht in [("0118-729 999", "tel:+31118729999"), ("0113 251 000", "tel:+31113251000"),
                                 ("0031113250555", "tel:+31113250555"), ("+31 115 553010", "tel:+31115553010")]:
            v = Vestiging(makelaar=m, straat="x", postcode="1234 AB", plaats="Goes", telefoon=invoer)
            self.assertEqual(v.telefoon_link, verwacht, invoer)


class GeocodeTest(TestCase):
    def test_alleen_exacte_treffer_in_dezelfde_plaats(self):
        from unittest import mock

        from .scraper import geocode

        antwoord = {"response": {"docs": [
            {"centroide_ll": "POINT(4.0 51.0)", "woonplaatsnaam": "Vlissingen", "postcode": "4381AA",
             "straatnaam": "Kerkstraat", "huisnummer": 1},
            {"centroide_ll": "POINT(3.61 51.50)", "woonplaatsnaam": "Middelburg", "postcode": "4331EN",
             "straatnaam": "Spanjaardstraat", "huisnummer": 13},
        ]}}
        sessie = mock.Mock()
        sessie.get.return_value.json.return_value = antwoord
        self.assertEqual(geocode.zoek("Spanjaardstraat 13", "", "Middelburg", sessie), (51.50, 3.61, "4331 EN"))
        self.assertIsNone(geocode.zoek("Spanjaardstraat 15", "", "Middelburg", sessie))


class VestigingTest(TestCase):
    def setUp(self):
        from .models import Vestiging
        self.m = Makelaar.objects.create(naam="K", aanbod_url="https://k.nl/")
        self.goes = Vestiging.objects.create(makelaar=self.m, naam="Goes", straat="a 1", postcode="4462 MV", plaats="Goes",
                                             telefoon="0113-227788", lat=51.50, lon=3.89)
        self.axel = Vestiging.objects.create(makelaar=self.m, naam="Axel", straat="b 2", postcode="4571 GD", plaats="Axel",
                                             telefoon="0115-553010", lat=51.27, lon=3.91)

    def test_kantoor_van_pagina(self):
        from .scraper.vestiging import bepaal
        w = Woning(makelaar=self.m, url="https://k.nl/1", woonplaats="Kats", lat=51.57, lon=3.88)
        # Beide nummers in een contactlijst, het Axelse één keer extra bij de woning
        cijfers = "0113227788" + "0115553010" + "0115553010"
        self.assertEqual(bepaal(w, cijfers), (self.axel, "pagina"))

    def test_geen_duidelijke_winnaar_dan_dichtstbij(self):
        from .scraper.vestiging import bepaal
        w = Woning(makelaar=self.m, url="https://k.nl/2", woonplaats="Kats", lat=51.57, lon=3.88)
        self.assertEqual(bepaal(w, "0113227788" + "0115553010"), (self.goes, "afstand"))
        self.assertEqual(bepaal(w, ""), (self.goes, "afstand"))


class CategorieTest(TestCase):
    def test_categorie(self):
        from .views import categorie
        self.assertEqual(categorie("appartement"), "appartement")
        self.assertEqual(categorie("tussenwoning"), "woning")
        self.assertEqual(categorie("overig"), "woning")
        self.assertEqual(categorie("bouwgrond"), "bouwgrond")


class NieuwLabelTest(TestCase):
    def test_nieuw(self):
        m = Makelaar.objects.create(naam="Test", aanbod_url="https://m.nl/")
        w = Woning.objects.create(makelaar=m, url="https://m.nl/1")
        self.assertTrue(w.is_nieuw)
        w.eerst_gezien = timezone.now() - timedelta(days=15)
        self.assertFalse(w.is_nieuw)
        w.eerst_gezien = timezone.now()
        w.eerste_import = True
        self.assertFalse(w.is_nieuw)
