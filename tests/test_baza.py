"""Testy bazy: duplikaty, pamiec "pierwszy raz", wygasanie, wyszukiwanie.

Wszystko na bazie w pamieci (:memory:) — nic nie dotyka jobradar.db.
"""

import json
import unittest

import baza
from portale import _oferta

T0 = 1_791_000_000  # "teraz" w testach
DZIEN = 86400


def oferta(id, portal, tytul="Junior Python Developer", firma="Acme sp. z o.o.", **pola):
    return _oferta(id=id, portal=portal, tytul=tytul, firma=firma,
                   url=f"https://{portal}.example/{id}", **pola)


def wynik(portal, *oferty, blad=None):
    return (portal, list(oferty), blad, 1.0)


class Klucz(unittest.TestCase):
    def test_ta_sama_oferta_z_roznymi_dopiskami(self):
        a = oferta("1", "pracuj", tytul="Java Developer (k/m)", firma="Sii Sp. z o.o.")
        b = oferta("2", "justjoin", tytul="Java Developer", firma="Sii")
        c = oferta("3", "protocol", tytul="Java Developer [remote]", firma="SII Polska")
        self.assertEqual(baza.klucz(a), baza.klucz(b))
        self.assertEqual(baza.klucz(a), baza.klucz(c))

    def test_inne_stanowisko_inny_klucz(self):
        a = oferta("1", "pracuj", tytul="Junior Java Developer")
        b = oferta("2", "pracuj", tytul="Senior Java Developer")
        self.assertNotEqual(baza.klucz(a), baza.klucz(b))

    def test_tresc_nawiasu_to_inne_stanowisko(self):
        a = oferta("1", "pracuj", tytul="System Analyst (Integration Architecture)")
        b = oferta("2", "pracuj", tytul="System Analyst")
        self.assertNotEqual(baza.klucz(a), baza.klucz(b))

    def test_inna_firma_inny_klucz(self):
        a = oferta("1", "pracuj", firma="Acme")
        b = oferta("2", "pracuj", firma="Globex")
        self.assertNotEqual(baza.klucz(a), baza.klucz(b))


class Scalanie(unittest.TestCase):
    def setUp(self):
        self.db = baza.polacz(":memory:")

    def ogloszenia(self):
        return [dict(r) for r in self.db.execute("SELECT * FROM ogloszenia")]

    def test_dwa_portale_jedno_ogloszenie(self):
        baza.zapisz_skan(self.db, [
            wynik("pracuj", oferta("pr-1", "pracuj", wid_od=8000, wid_do=10000,
                                   stack=["Python"], miasta=["Warszawa"], data=T0 - 100)),
            wynik("justjoin", oferta("jj-1", "justjoin", wid_od=7000, wid_do=9000,
                                     stack=["python", "Django"], tryby=["zdalna"], data=T0)),
        ], teraz=T0)
        [g] = self.ogloszenia()
        self.assertEqual(json.loads(g["portale"]), ["justjoin", "pracuj"])  # wg priorytetu
        self.assertEqual(len(json.loads(g["linki"])), 2)
        self.assertEqual((g["wid_od"], g["wid_do"]), (7000, 10000))
        self.assertEqual(json.loads(g["stack"]), ["python", "Django"])  # bez dubla "Python"
        self.assertEqual(g["data"], T0 - 100)  # PIERWSZA publikacja (na Pracuj)

    def test_outsourcing_rozne_oferty_pod_tym_samym_tytulem(self):
        # SCALO: dwa rozne "System Analyst" na JJ + ich kopie na Pracuj/theprotocol
        baza.zapisz_skan(self.db, [
            wynik("justjoin", oferta("jj-1", "justjoin", tytul="System Analyst", firma="SCALO", wid_od=16000, wid_do=19200),
                              oferta("jj-2", "justjoin", tytul="System Analyst", firma="SCALO", wid_od=20800, wid_do=25200)),
            wynik("pracuj", oferta("pr-1", "pracuj", tytul="System Analyst (k/m)", firma="SCALO Sp. z o.o.", wid_od=16000, wid_do=19200)),
            wynik("protocol", oferta("tp-1", "protocol", tytul="System Analyst", firma="SCALO", wid_od=16000, wid_do=19200)),
        ], teraz=T0)
        grupy = sorted(json.loads(g["portale"]) for g in self.ogloszenia())
        self.assertEqual(grupy, [["justjoin"], ["justjoin", "pracuj", "protocol"]])

    def test_niejednoznaczne_bez_widelek_zostaja_osobno(self):
        baza.zapisz_skan(self.db, [
            wynik("justjoin", oferta("jj-1", "justjoin"), oferta("jj-2", "justjoin")),
            wynik("nofluff", oferta("nf-1", "nofluff")),
        ], teraz=T0)
        self.assertEqual(len(self.ogloszenia()), 3)

    def test_bulldog_bez_daty_z_pierwszego_skanu_ma_nieznany_wiek(self):
        baza.zapisz_skan(self.db, [wynik("bulldog", oferta("bd-1", "bulldog"))], teraz=T0)
        self.assertEqual(self.ogloszenia()[0]["data"], 0)

    def test_bulldog_bez_daty_pozniej_dostaje_pierwszy_raz(self):
        stara = oferta("bd-1", "bulldog", tytul="Stara")
        nowa = oferta("bd-2", "bulldog", tytul="Nowa")
        baza.zapisz_skan(self.db, [wynik("bulldog", stara)], teraz=T0)
        baza.zapisz_skan(self.db, [wynik("bulldog", stara, nowa)], teraz=T0 + DZIEN)
        daty = {g["tytul"]: g["data"] for g in self.ogloszenia()}
        self.assertEqual(daty, {"Stara": 0, "Nowa": T0 + DZIEN})


class Pamiec(unittest.TestCase):
    def setUp(self):
        self.db = baza.polacz(":memory:")

    def test_pierwszy_raz_nie_zmienia_sie_przy_kolejnych_skanach(self):
        o = oferta("jj-1", "justjoin")
        nowe1 = baza.zapisz_skan(self.db, [wynik("justjoin", o)], teraz=T0)
        nowe2 = baza.zapisz_skan(self.db, [wynik("justjoin", o)], teraz=T0 + DZIEN)
        self.assertEqual((nowe1["justjoin"], nowe2["justjoin"]), (1, 0))
        r = self.db.execute("SELECT pierwszy_raz, ostatnio FROM oferty").fetchone()
        self.assertEqual(tuple(r), (T0, T0 + DZIEN))

    def test_log_skanow(self):
        baza.zapisz_skan(self.db, [wynik("nofluff", blad="HTTPError 503")], teraz=T0)
        r = self.db.execute("SELECT portal, blad FROM skany").fetchone()
        self.assertEqual(tuple(r), ("nofluff", "HTTPError 503"))


class Wygasanie(unittest.TestCase):
    def setUp(self):
        self.db = baza.polacz(":memory:")
        self.oferty = [oferta(f"nf-{i}", "nofluff", tytul=f"Stanowisko {i}") for i in range(10)]
        baza.zapisz_skan(self.db, [wynik("nofluff", *self.oferty)], teraz=T0)

    def aktywne(self):
        return {r[0] for r in self.db.execute("SELECT id FROM oferty WHERE aktywna=1")}

    def test_skan_wygasza_znikniete(self):
        baza.zapisz_skan(self.db, [wynik("nofluff", *self.oferty[:8])], teraz=T0 + DZIEN)
        self.assertEqual(len(self.aktywne()), 8)
        self.assertEqual(baza.statystyki(self.db)["ogloszen"], 8)

    def test_blad_portalu_niczego_nie_wygasza(self):
        baza.zapisz_skan(self.db, [wynik("nofluff", blad="timeout")], teraz=T0 + DZIEN)
        self.assertEqual(len(self.aktywne()), 10)

    def test_bezpiecznik_podejrzanie_malo_ofert(self):
        baza.zapisz_skan(self.db, [wynik("nofluff", *self.oferty[:3])], teraz=T0 + DZIEN)
        self.assertEqual(len(self.aktywne()), 10)

    def test_oferta_wraca_po_wygasnieciu(self):
        baza.zapisz_skan(self.db, [wynik("nofluff", *self.oferty[:8])], teraz=T0 + DZIEN)
        baza.zapisz_skan(self.db, [wynik("nofluff", *self.oferty)], teraz=T0 + 2 * DZIEN)
        self.assertEqual(len(self.aktywne()), 10)

    def test_data_wygasniecia_w_przeszlosci(self):
        stara = oferta("jj-x", "justjoin", wygasa=T0 + DZIEN)
        baza.zapisz_skan(self.db, [wynik("justjoin", stara)], teraz=T0 + 2 * DZIEN)
        self.assertNotIn("jj-x", self.aktywne())


class MojeDecyzje(unittest.TestCase):
    def setUp(self):
        self.db = baza.polacz(":memory:")
        baza.zapisz_skan(self.db, [wynik("pracuj", oferta("pr-1", "pracuj"))], teraz=T0)

    def status(self, tytul="Junior Python Developer"):
        return next(g["status"] for g in baza.lista(self.db) if g["tytul"] == tytul)

    def test_zaaplikowane_i_cofniecie(self):
        baza.ustaw_status(self.db, "pr-1", "aplikowane")
        self.assertEqual(self.status(), "aplikowane")
        baza.ustaw_status(self.db, "pr-1", None)
        self.assertIsNone(self.status())

    def test_status_przezywa_zmiane_glownej_oferty(self):
        # ukrywam oferte z Pracuj; potem ta sama pojawia sie na JustJoin, ktory
        # ma wyzszy priorytet -> ogloszenie dostaje nowe id, ale status zostaje
        baza.ustaw_status(self.db, "pr-1", "ukryte")
        baza.zapisz_skan(self.db, [wynik("pracuj", oferta("pr-1", "pracuj")),
                                   wynik("justjoin", oferta("jj-1", "justjoin"))],
                         teraz=T0 + DZIEN)
        [g] = baza.lista(self.db)
        self.assertEqual(g["id"], "jj-1")
        self.assertEqual(g["status"], "ukryte")

    def test_nieznany_status(self):
        with self.assertRaises(ValueError):
            baza.ustaw_status(self.db, "pr-1", "cokolwiek")

    def test_nowe_do_przejrzenia(self):
        self.assertTrue(baza.lista(self.db)[0]["nowe"])
        baza.zapisz_ustawienie(self.db, "przejrzane", T0)
        self.assertFalse(baza.lista(self.db)[0]["nowe"])
        baza.zapisz_skan(self.db, [wynik("pracuj", oferta("pr-1", "pracuj"),
                                         oferta("pr-2", "pracuj", tytul="Stażysta QA"))],
                         teraz=T0 + DZIEN)
        nowe = {g["tytul"]: g["nowe"] for g in baza.lista(self.db)}
        self.assertEqual(nowe, {"Junior Python Developer": False, "Stażysta QA": True})


class Dziennik(unittest.TestCase):
    """Dziennik aplikacji: kopia oferty, etapy, przypomnienia, wpisy reczne."""

    def setUp(self):
        self.db = baza.polacz(":memory:")
        baza.zapisz_skan(self.db, [wynik("pracuj", oferta("pr-1", "pracuj", wid_od=6000, wid_do=8000,
                                                         miasta=["Warszawa"], stack=["Python"]))],
                         teraz=T0)

    def test_zaaplikowalem_zaklada_wpis_z_kopia_oferty(self):
        baza.ustaw_status(self.db, "pr-1", "aplikowane", teraz=T0)
        [a] = baza.aplikacje(self.db)
        self.assertEqual((a["tytul"], a["firma"], a["lokacja"]),
                         ("Junior Python Developer", "Acme sp. z o.o.", "Warszawa"))
        self.assertEqual((a["wid_od"], a["wid_do"], a["stack"]), (6000, 8000, ["Python"]))
        self.assertEqual(a["etap"], "wyslane")
        self.assertEqual(a["nastepny_krok"], T0 + baza.FOLLOW_UP_S)  # follow-up za tydzien
        self.assertTrue(a["aktywna"])

    def test_drugie_klikniecie_nie_dubluje(self):
        baza.ustaw_status(self.db, "pr-1", "aplikowane")
        baza.ustaw_status(self.db, "pr-1", "aplikowane")
        self.assertEqual(len(baza.aplikacje(self.db)), 1)

    def test_cofniecie_usuwa_wpis(self):
        baza.ustaw_status(self.db, "pr-1", "aplikowane")
        baza.ustaw_status(self.db, "pr-1", None)
        self.assertEqual(baza.aplikacje(self.db), [])

    def test_wpis_zostaje_po_wygasnieciu_oferty(self):
        baza.ustaw_status(self.db, "pr-1", "aplikowane")
        baza.zapisz_skan(self.db, [wynik("pracuj", oferta("pr-2", "pracuj", tytul="Stażysta QA"))],
                         teraz=T0 + DZIEN)
        [a] = baza.aplikacje(self.db)
        self.assertEqual(a["tytul"], "Junior Python Developer")
        self.assertFalse(a["aktywna"])

    def test_etapy_ida_do_historii_a_zamkniecie_kasuje_przypomnienie(self):
        baza.ustaw_status(self.db, "pr-1", "aplikowane", teraz=T0)
        [a] = baza.aplikacje(self.db)
        baza.zmien_aplikacje(self.db, a["id"], etap="rozmowa", notatki="HR w czwartek", teraz=T0 + DZIEN)
        baza.zmien_aplikacje(self.db, a["id"], etap="odmowa", teraz=T0 + 5 * DZIEN)
        [a] = baza.aplikacje(self.db)
        self.assertEqual([h["etap"] for h in a["historia"]], ["wyslane", "rozmowa", "odmowa"])
        self.assertEqual(a["notatki"], "HR w czwartek")
        self.assertIsNone(a["nastepny_krok"])

    def test_zle_pola_i_etapy(self):
        baza.ustaw_status(self.db, "pr-1", "aplikowane")
        [a] = baza.aplikacje(self.db)
        with self.assertRaises(ValueError):
            baza.zmien_aplikacje(self.db, a["id"], etap="cokolwiek")
        with self.assertRaises(ValueError):
            baza.zmien_aplikacje(self.db, a["id"], idy="[]")

    def test_reczny_wpis_spoza_radaru(self):
        id_ = baza.dodaj_aplikacje(self.db, "Analityk SOC", "Wojska Obrony Cyberprzestrzeni",
                                   kiedy=T0 - DZIEN, teraz=T0)
        [a] = baza.aplikacje(self.db)
        self.assertEqual(a["id"], id_)
        self.assertEqual(a["kiedy"], T0 - DZIEN)
        self.assertIsNone(a["aktywna"])
        with self.assertRaises(ValueError):
            baza.dodaj_aplikacje(self.db, " ", "Firma")

    def test_usuniecie_wpisu_zwraca_oferte_do_przejrzenia(self):
        baza.ustaw_status(self.db, "pr-1", "aplikowane")
        [a] = baza.aplikacje(self.db)
        baza.usun_aplikacje(self.db, a["id"])
        self.assertEqual(baza.aplikacje(self.db), [])
        self.assertIsNone(baza.lista(self.db)[0]["status"])


if __name__ == "__main__":
    unittest.main()
