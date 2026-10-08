"""Testy parserow portali — bez sieci, na zapisanych probkach (tests/fixtury).

Uruchomienie:  py -m unittest -v

Fixtury to wycinki prawdziwych odpowiedzi z 2026-10-08. Gdy portal zmieni
format i skan zacznie zwracac smieci: zapisz nowa odpowiedz jako fixture,
popraw parser, az testy znow przejda.
"""

import json
import unittest
from pathlib import Path

import portale

FIXTURY = Path(__file__).parent / "fixtury"
POLA = {"id", "portal", "tytul", "firma", "url", "miasta", "lokacja", "data",
        "wygasa", "poziomy", "tryby", "umowy", "wid_od", "wid_do", "stack", "kategoria"}


def wczytaj(nazwa):
    return json.loads((FIXTURY / f"{nazwa}.json").read_text(encoding="utf-8"))


def po_tytule(oferty, fragment):
    return next(o for o in oferty if fragment in o["tytul"])


class WspolnyFormat(unittest.TestCase):
    """Kazdy portal musi oddawac ten sam ksztalt oferty — na tym stoi wyszukiwarka."""

    def test_kazdy_portal_ma_wszystkie_pola(self):
        for nazwa in portale.PORTALE:
            with self.subTest(portal=nazwa):
                oferty = getattr(portale, f"parsuj_{nazwa}")(wczytaj(nazwa))
                self.assertTrue(oferty)
                for o in oferty:
                    self.assertEqual(set(o), POLA)
                    self.assertEqual(o["portal"], nazwa)
                    self.assertTrue(o["id"] and o["tytul"] and o["firma"])
                    self.assertTrue(o["url"].startswith("https://"))
                    self.assertLessEqual(set(o["poziomy"]), {"staz", "junior", "mid", "senior", "lead"})
                    self.assertLessEqual(set(o["tryby"]), {"zdalna", "hybrydowa", "biuro"})
                    self.assertLessEqual(set(o["umowy"]), {"b2b", "uop", "zlecenie", "staz", "inna"})


class JustJoin(unittest.TestCase):
    def setUp(self):
        self.oferty = portale.parsuj_justjoin(wczytaj("justjoin"))

    def test_stawka_godzinowa_juz_przeliczona_na_miesiac(self):
        # 90-100 zl/h; JJ sam podaje "from" w skali miesiaca — nie mnozymy drugi raz
        o = po_tytule(self.oferty, "Business Analyst")
        self.assertEqual((o["wid_od"], o["wid_do"]), (15120, 16800))

    def test_wiele_lokalizacji_i_zdalna(self):
        o = po_tytule(self.oferty, "Cloud Support Lead")
        self.assertIn("Warszawa", o["miasta"])
        self.assertEqual(len(o["miasta"]), 5)
        self.assertEqual(o["tryby"], ["zdalna"])

    def test_data_to_pierwsza_publikacja_nie_odswiezenie(self):
        # publishedAt = 2026-10-08 (bump), lastPublishedAt = 2026-09-18 (prawdziwa)
        o = po_tytule(self.oferty, "Junior Site Reliability")
        self.assertEqual(o["data"], portale._ts("2026-09-18T13:19:39.412237Z"))

    def test_daty(self):
        o = po_tytule(self.oferty, "Junior Site Reliability")
        self.assertEqual(o["poziomy"], ["junior"])
        self.assertGreater(o["data"], 0)
        self.assertGreater(o["wygasa"], o["data"])


class NoFluff(unittest.TestCase):
    def setUp(self):
        self.oferty = portale.parsuj_nofluff(wczytaj("nofluff"))

    def test_id_z_reference_wspolne_dla_miast(self):
        o = po_tytule(self.oferty, "SAP MM")
        self.assertEqual(o["id"], "nf-QA8YVLXQ")
        self.assertTrue(o["url"].startswith("https://nofluffjobs.com/pl/job/"))

    def test_tryby_zdalna_hybryda_i_brak(self):
        self.assertEqual(po_tytule(self.oferty, "SAP MM")["tryby"], ["zdalna"])
        self.assertEqual(po_tytule(self.oferty, "Senior Java")["tryby"], ["hybrydowa"])
        self.assertEqual(po_tytule(self.oferty, "Serwisant")["tryby"], [])

    def test_widelki_i_umowa(self):
        o = po_tytule(self.oferty, "SAP MM")
        self.assertEqual((o["wid_od"], o["wid_do"]), (25200, 30240))
        self.assertEqual(o["umowy"], ["b2b"])


class Pracuj(unittest.TestCase):
    def setUp(self):
        self.oferty = portale.parsuj_pracuj(wczytaj("pracuj"))

    def test_widelki_godzinowe_z_tekstu(self):
        # "100–130 zł netto (+ VAT) / godz." -> x168
        o = po_tytule(self.oferty, "AxiomSL")
        self.assertEqual((o["wid_od"], o["wid_do"]), (16800, 21840))

    def test_widelki_miesieczne_z_tekstu(self):
        o = po_tytule(self.oferty, "Solution Architect Intern")
        self.assertEqual((o["wid_od"], o["wid_do"]), (5000, 7000))
        self.assertEqual(o["poziomy"], ["staz"])

    def test_oferta_w_wielu_miastach_linkuje_do_warszawy(self):
        o = po_tytule(self.oferty, "C++ Embedded")
        self.assertIn("Warszawa", o["miasta"])
        self.assertIn("warszawa", o["url"])

    def test_data_to_initial_publicated(self):
        # odswiezona 2026-10-08, ale wisi od 2026-09-23
        o = po_tytule(self.oferty, "Solution Architect Intern")
        self.assertEqual(o["data"], portale._ts("2026-09-23T14:30:47.987Z"))

    def test_kilka_poziomow(self):
        self.assertEqual(po_tytule(self.oferty, "Tester manualny")["poziomy"], ["junior", "mid"])

    def test_liczba_stron(self):
        self.assertEqual(portale._pracuj_ile_stron(wczytaj("pracuj")), 3)


class Protocol(unittest.TestCase):
    def setUp(self):
        self.oferty = portale.parsuj_protocol(wczytaj("protocol"))

    def test_stawka_godzinowa(self):
        self.assertEqual(po_tytule(self.oferty, "Fullstack Developer")["wid_do"], 155 * 168)

    def test_umowa_o_prace_miesieczna(self):
        o = po_tytule(self.oferty, "Senior Dev Engineer")
        self.assertEqual(o["umowy"], ["uop"])
        self.assertEqual((o["wid_od"], o["wid_do"]), (15000, 20000))

    def test_data_bez_strefy_to_utc(self):
        self.assertEqual(portale._ts("2026-10-08T14:27:55.04"), 1791469675)


class Bulldog(unittest.TestCase):
    def setUp(self):
        self.oferty = portale.parsuj_bulldog(wczytaj("bulldog"))

    def test_widelki_z_tekstu(self):
        o = po_tytule(self.oferty, "Senior Test Analyst")
        self.assertEqual((o["wid_od"], o["wid_do"]), (12000, 16000))

    def test_lista_bez_daty_publikacji(self):
        # lista jej nie podaje — dociagamy ze strony oferty (nizej)
        self.assertTrue(all(o["data"] == 0 for o in self.oferty))

    def test_daty_ze_strony_oferty(self):
        data, wygasa = portale.parsuj_bulldog_szczegoly(wczytaj("bulldog_oferta"))
        self.assertEqual(data, portale._ts("2026-10-08T08:20:27+02:00"))
        self.assertEqual(wygasa, portale._ts("2026-11-07T23:59:59+01:00"))

    def test_miasta_z_listy_po_przecinku(self):
        self.assertIn("Warszawa", po_tytule(self.oferty, "Fullstack Mobile")["miasta"])


class Normalizacja(unittest.TestCase):
    def test_literowka_w_widelkach_odrzucona(self):
        o = portale._oferta(wid_od=21840, wid_do=3276000)
        self.assertEqual((o["wid_od"], o["wid_do"]), (21840, None))

    def test_dla_mnie_warszawa_albo_zdalna(self):
        dla_mnie = lambda **p: portale._dla_mnie(portale._oferta(poziomy=["junior"], **p))
        self.assertTrue(dla_mnie(miasta=["Warsaw"]))
        self.assertTrue(dla_mnie(miasta=["Kraków"], tryby=["zdalna"]))
        self.assertFalse(dla_mnie(miasta=["Kraków"], tryby=["hybrydowa"]))

    def test_dla_mnie_tylko_staz_i_junior(self):
        dla_mnie = lambda poziomy: portale._dla_mnie(portale._oferta(poziomy=poziomy, miasta=["Warszawa"]))
        self.assertTrue(dla_mnie(["staz"]))
        self.assertTrue(dla_mnie(["junior", "mid"]))  # "junior/mid" tez jest dla Ciebie
        self.assertFalse(dla_mnie(["mid"]))
        self.assertFalse(dla_mnie(["senior"]))

    def test_justjoin_7_cyfr_ulamka(self):
        self.assertGreater(portale._ts("2026-10-08T14:20:01.8875973Z"), 0)


if __name__ == "__main__":
    unittest.main()
