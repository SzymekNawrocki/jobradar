"""Baza ofert (SQLite) — pamiec, duplikaty, wygasanie.

  oferty      — surowe oferty, jedna na (portal, id). Tu pamietamy, kiedy
                radar zobaczyl oferte PIERWSZY raz i kiedy OSTATNI.
  ogloszenia  — oferty scalone miedzy portalami: ta sama firma + ten sam
                tytul = jedno ogloszenie z kilkoma linkami ("na 3 portalach").
                Przebudowywane po kazdym skanie — z tego czyta strona.
  skany       — log skanow: kiedy, ktory portal, ile ofert, jaki blad.

Wygasanie: kazdy skan to pelna lista entry-level z portalu, wiec oferty,
ktorych w nim nie bylo, zniknely z portalu -> nieaktywne. Oferty z data
"wygasa" w przeszlosci tez wypadaja.
"""

import json
import re
import sqlite3
import time
from pathlib import Path

PLIK = Path(__file__).parent / "jobradar.db"

# przy scalaniu tytul/firme/glowny link bierzemy z pierwszego portalu na liscie
PRIORYTET = ["justjoin", "nofluff", "pracuj", "protocol", "bulldog", "solid", "linkedin"]

SCHEMAT = """
CREATE TABLE IF NOT EXISTS oferty (
    id           TEXT PRIMARY KEY,
    portal       TEXT NOT NULL,
    klucz        TEXT NOT NULL,
    tytul        TEXT, firma TEXT, url TEXT,
    miasta       TEXT, poziomy TEXT, tryby TEXT, umowy TEXT, stack TEXT,
    kategoria    TEXT,
    wid_od       INTEGER, wid_do INTEGER,
    data         INTEGER, wygasa INTEGER,
    pierwszy_raz INTEGER NOT NULL,
    ostatnio     INTEGER NOT NULL,
    aktywna      INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX IF NOT EXISTS oferty_klucz ON oferty(klucz);

CREATE TABLE IF NOT EXISTS ogloszenia (
    id           TEXT PRIMARY KEY,  -- id glownej oferty (wg PRIORYTET)
    idy          TEXT,           -- id wszystkich scalonych ofert (do statusow)
    tytul        TEXT, firma TEXT, url TEXT,
    linki        TEXT,           -- [{"portal": ..., "url": ...}, ...]
    portale      TEXT,           -- ["justjoin", "pracuj"]
    miasta       TEXT, poziomy TEXT, tryby TEXT, umowy TEXT, stack TEXT,
    kategoria    TEXT,
    wid_od       INTEGER, wid_do INTEGER,
    data         INTEGER,        -- publikacja (albo pierwszy_raz, gdy portal nie podaje)
    wygasa       INTEGER,
    pierwszy_raz INTEGER
);

CREATE TABLE IF NOT EXISTS skany (
    start   INTEGER NOT NULL,
    portal  TEXT NOT NULL,
    ile     INTEGER NOT NULL,
    nowych  INTEGER NOT NULL,
    blad    TEXT,
    sekundy REAL
);

-- moje decyzje. Per SUROWA oferta, nie per ogloszenie: ogloszenia sa
-- przebudowywane co skan i ich id moze sie zmienic (np. gdy ta sama
-- oferta pojawi sie pozniej na JustJoin, ktory ma wyzszy priorytet).
CREATE TABLE IF NOT EXISTS moje (
    id_oferty TEXT PRIMARY KEY,
    status    TEXT NOT NULL,     -- 'aplikowane' / 'ukryte'
    kiedy     INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS ustawienia (
    nazwa   TEXT PRIMARY KEY,
    wartosc TEXT
);
"""

POLA_LISTOWE = ("miasta", "poziomy", "tryby", "umowy", "stack")
MIN_CZESC_PELNEGO = 0.5
STATUSY = ("aplikowane", "ukryte")


def polacz(plik=PLIK, check_same_thread=True):
    db = sqlite3.connect(plik, check_same_thread=check_same_thread)
    db.row_factory = sqlite3.Row
    # ogloszenia to tabela pochodna — budujemy ja od nowa przy kazdym polaczeniu,
    # wiec zmiana jej kolumn nie wymaga migracji ani kasowania bazy
    db.execute("DROP TABLE IF EXISTS ogloszenia")
    db.executescript(SCHEMAT)
    with db:
        przebuduj_ogloszenia(db)
    return db


# --------------------------------------------------------------------------
# klucz duplikatu: firma + tytul po "wyczyszczeniu"
# --------------------------------------------------------------------------

# Dopiski, ktore rozni pracodawcy doklejaja do TEGO SAMEGO stanowiska: plec
# i tryb pracy. Reszty nawiasow NIE wycinamy — "System Analyst (Integration
# Architecture)" to inne stanowisko niz "System Analyst".
_DOPISKI_TYTULU = re.compile(
    r"\b(k/m/x|k/m|m/k|f/m/x|m/f/d|m/w/d|m/f|f/m|she/he/they|he/she/they|he/she|she/he|"
    r"ona/on|on/ona|remote|zdalnie|zdalna|hybrid|hybrydowo|hybrydowa)\b")
_FORMY_PRAWNE = re.compile(
    r"\b(sp\.?\s*z\s*o\.?\s*o\.?|s\.?\s*a\.?|sp\.?\s*k\.?|sp\.?\s*j\.?|spółka.*|"
    r"inc\.?|ltd\.?|llc|gmbh|poland|polska|group)(?=\W|$)")


def _sam_tekst(s):
    return re.sub(r"[^0-9a-ząćęłńóśźż]+", "", s)


def klucz(o):
    """'emplo|netdeveloper' — wspolny dla tej samej oferty na roznych portalach."""
    tytul = _DOPISKI_TYTULU.sub(" ", (o["tytul"] or "").lower())
    firma = _FORMY_PRAWNE.sub(" ", (o["firma"] or "").lower())
    return f"{_sam_tekst(firma)}|{_sam_tekst(tytul)}"


# --------------------------------------------------------------------------
# zapis skanu
# --------------------------------------------------------------------------

def zapisz_skan(db, wyniki, teraz=None):
    """Zapisuje wynik skanu: [(portal, oferty, blad, sekundy), ...].

    Zwraca liczbe NOWYCH ofert (pierwszy raz widzianych) na portal.
    """
    teraz = teraz or int(time.time())
    nowe = {}
    with db:
        for portal, oferty, blad, sek in wyniki:
            znane = {r[0] for r in db.execute("SELECT id FROM oferty WHERE portal=?", (portal,))}
            aktywnych = db.execute("SELECT COUNT(*) FROM oferty WHERE portal=? AND aktywna=1",
                                   (portal,)).fetchone()[0]
            nowe[portal] = sum(1 for o in oferty if o["id"] not in znane)
            for o in oferty:
                _upsert(db, o, teraz)
            # skan bez bledu = pelna lista portalu -> reszta zniknela.
            # Bezpiecznik: gdy portal nagle oddal < polowy tego, co mial, to raczej
            # zmienil strone/filtr niz zdjal oferty — wtedy niczego nie wygaszamy.
            if not blad and len(oferty) >= MIN_CZESC_PELNEGO * aktywnych:
                db.execute("UPDATE oferty SET aktywna=0 WHERE portal=? AND ostatnio<?",
                           (portal, teraz))
            db.execute("INSERT INTO skany VALUES (?,?,?,?,?,?)",
                       (teraz, portal, len(oferty), nowe[portal], blad, sek))
        db.execute("UPDATE oferty SET aktywna=0 WHERE wygasa>0 AND wygasa<?", (teraz,))
        przebuduj_ogloszenia(db)
    return nowe


def _upsert(db, o, teraz):
    wiersz = {k: o[k] for k in ("id", "portal", "tytul", "firma", "url", "kategoria",
                                "wid_od", "wid_do", "data", "wygasa")}
    wiersz.update({k: json.dumps(o[k], ensure_ascii=False) for k in POLA_LISTOWE})
    wiersz.update(klucz=klucz(o), teraz=teraz)
    db.execute("""
        INSERT INTO oferty (id, portal, klucz, tytul, firma, url, miasta, poziomy,
                            tryby, umowy, stack, kategoria, wid_od, wid_do, data,
                            wygasa, pierwszy_raz, ostatnio, aktywna)
        VALUES (:id, :portal, :klucz, :tytul, :firma, :url, :miasta, :poziomy,
                :tryby, :umowy, :stack, :kategoria, :wid_od, :wid_do, :data,
                :wygasa, :teraz, :teraz, 1)
        ON CONFLICT(id) DO UPDATE SET
            klucz=excluded.klucz, tytul=excluded.tytul, firma=excluded.firma,
            url=excluded.url, miasta=excluded.miasta, poziomy=excluded.poziomy,
            tryby=excluded.tryby, umowy=excluded.umowy, stack=excluded.stack,
            kategoria=excluded.kategoria, wid_od=excluded.wid_od,
            wid_do=excluded.wid_do, data=excluded.data, wygasa=excluded.wygasa,
            ostatnio=excluded.ostatnio, aktywna=1
    """, wiersz)


# --------------------------------------------------------------------------
# scalanie duplikatow
# --------------------------------------------------------------------------

def _scal_liste(wartosci):
    """Suma list bez powtorzen (bez patrzenia na wielkosc liter), kolejnosc zachowana."""
    widziane, wynik = set(), []
    for lista in wartosci:
        for x in lista:
            if x and x.lower() not in widziane:
                widziane.add(x.lower())
                wynik.append(x)
    return wynik


def scal(oferty, start_portalu=None):
    """Kilka ofert z tym samym kluczem -> jedno ogloszenie (slownik).

    start_portalu: {portal: ts pierwszego udanego skanu} — patrz _data_awaryjna.
    """
    oferty = sorted(oferty, key=lambda o: (PRIORYTET.index(o["portal"])
                                           if o["portal"] in PRIORYTET else 99))
    glowna = oferty[0]
    od = [o["wid_od"] for o in oferty if o["wid_od"]]
    do = [o["wid_do"] for o in oferty if o["wid_do"]]
    pierwszy = min(o["pierwszy_raz"] for o in oferty)
    # pierwsza publikacja na KTORYMKOLWIEK portalu — oferta wrzucona na Pracuj
    # tydzien temu nie jest "swieza" tylko dlatego, ze dzis trafila na JustJoin
    data = min((o["data"] for o in oferty if o["data"]), default=0) or max(
        _data_awaryjna(o, start_portalu or {}) for o in oferty)
    return {
        # nie klucz — jeden klucz moze dac kilka ogloszen (patrz grupuj)
        "id": glowna["id"],
        "idy": [o["id"] for o in oferty],
        "tytul": glowna["tytul"],
        "firma": glowna["firma"],
        "url": glowna["url"],
        "linki": [{"portal": o["portal"], "url": o["url"]} for o in oferty],
        "portale": _scal_liste([[o["portal"]] for o in oferty]),
        **{k: _scal_liste(o[k] for o in oferty) for k in POLA_LISTOWE},
        "kategoria": next((o["kategoria"] for o in oferty if o["kategoria"]), ""),
        "wid_od": min(od) if od else None,
        "wid_do": max(do) if do else None,
        "data": data,
        "wygasa": max(o["wygasa"] for o in oferty),
        "pierwszy_raz": pierwszy,
    }


def _data_awaryjna(o, start_portalu):
    """Data dla oferty bez daty publikacji (Bulldog): kiedy radar ja zobaczyl.

    Ale tylko jesli pojawila sie PO pierwszym skanie portalu. To, co wisialo
    na portalu juz przy pierwszym skanie, ma nieznany wiek -> 0 (na koniec
    listy), inaczej cala startowa paczka udawalaby "dzisiejsze" oferty.
    """
    if o["pierwszy_raz"] > start_portalu.get(o["portal"], 0):
        return o["pierwszy_raz"]
    return 0


def grupuj(oferty):
    """Dzieli oferty na ogloszenia (listy ofert do scalenia).

    Ten sam klucz to jeszcze nie ta sama oferta: firmy outsourcingowe wystawiaja
    dziesiatki ROZNYCH "System Analyst" (inny projekt, inne widelki). Zasady:
      1. W jednym ogloszeniu max jedna oferta z danego portalu — dwa rozne id
         z tego samego portalu to dwie rozne oferty (portal sam je rozroznia).
      2. Gdy pod kluczem jest kilka ofert z jednego portalu, dzielimy po
         widelkach (ta sama oferta na Pracuj i theprotocol ma identyczne).
      3. Co dalej niejednoznaczne — zostaje osobno. Lepiej pokazac duplikat
         niz skleic dwie rozne oferty i jedna zgubic.
    """
    po_kluczu = {}
    for o in oferty:
        po_kluczu.setdefault(o["klucz"], []).append(o)

    wynik = []
    for grupa in po_kluczu.values():
        if _po_jednej_z_portalu(grupa):
            wynik.append(grupa)
            continue
        po_widelkach = {}
        for o in grupa:
            k = (o["wid_od"], o["wid_do"]) if o["wid_do"] else o["id"]
            po_widelkach.setdefault(k, []).append(o)
        for podgrupa in po_widelkach.values():
            if _po_jednej_z_portalu(podgrupa):
                wynik.append(podgrupa)
            else:
                wynik.extend([o] for o in podgrupa)
    return wynik


def _po_jednej_z_portalu(grupa):
    portale = [o["portal"] for o in grupa]
    return len(portale) == len(set(portale))


def _wczytaj_oferte(r):
    o = dict(r)
    for k in POLA_LISTOWE:
        o[k] = json.loads(o[k] or "[]")
    return o


def przebuduj_ogloszenia(db):
    """Skleja aktywne oferty w ogloszenia.

    Przebudowa od zera (kilkaset wierszy) trwa ulamek sekundy, a oszczedza
    calej logiki "co sie zmienilo".
    """
    start_portalu = dict(db.execute(
        "SELECT portal, MIN(start) FROM skany WHERE blad IS NULL GROUP BY portal"))
    oferty = [_wczytaj_oferte(r) for r in db.execute("SELECT * FROM oferty WHERE aktywna=1")]

    db.execute("DELETE FROM ogloszenia")
    for grupa in grupuj(oferty):
        g = scal(grupa, start_portalu)
        wiersz = {k: (json.dumps(v, ensure_ascii=False) if isinstance(v, list) else v)
                  for k, v in g.items()}
        db.execute(f"INSERT INTO ogloszenia ({', '.join(wiersz)}) "
                   f"VALUES ({', '.join(':' + k for k in wiersz)})", wiersz)


# --------------------------------------------------------------------------
# odczyt
# --------------------------------------------------------------------------

def lista(db):
    """Wszystkie ogloszenia dla strony, z moim statusem i flaga "nowe".

    "Nowe" = radar zobaczyl je po tym, jak ostatnio kliknales "Przejrzane".
    """
    przejrzane = int(ustawienie(db, "przejrzane") or 0)
    statusy = {r["id_oferty"]: r["status"] for r in db.execute("SELECT * FROM moje")}
    wynik = []
    for r in db.execute("SELECT * FROM ogloszenia ORDER BY data DESC, pierwszy_raz DESC"):
        g = dict(r)
        for k in ("idy", "linki", "portale") + POLA_LISTOWE:
            g[k] = json.loads(g[k] or "[]")
        g["status"] = next((statusy[i] for i in g["idy"] if i in statusy), None)
        g["nowe"] = g["pierwszy_raz"] > przejrzane
        wynik.append(g)
    return wynik


def ustaw_status(db, id_ogloszenia, status, teraz=None):
    """Zapisuje status dla wszystkich ofert ogloszenia. status=None cofa decyzje."""
    if status is not None and status not in STATUSY:
        raise ValueError(f"nieznany status: {status}")
    r = db.execute("SELECT idy FROM ogloszenia WHERE id=?", (id_ogloszenia,)).fetchone()
    if r is None:
        raise KeyError(id_ogloszenia)
    idy = json.loads(r["idy"])
    with db:
        db.executemany("DELETE FROM moje WHERE id_oferty=?", [(i,) for i in idy])
        if status:
            db.executemany("INSERT INTO moje VALUES (?,?,?)",
                           [(i, status, teraz or int(time.time())) for i in idy])


def ustawienie(db, nazwa):
    r = db.execute("SELECT wartosc FROM ustawienia WHERE nazwa=?", (nazwa,)).fetchone()
    return r[0] if r else None


def zapisz_ustawienie(db, nazwa, wartosc):
    with db:
        db.execute("INSERT INTO ustawienia VALUES (?,?) "
                   "ON CONFLICT(nazwa) DO UPDATE SET wartosc=excluded.wartosc",
                   (nazwa, str(wartosc)))


def ostatni_skan(db):
    """(kiedy, [bledy]) ostatniego skanu — do paska na stronie."""
    r = db.execute("SELECT MAX(start) FROM skany").fetchone()
    if not r or r[0] is None:
        return None, []
    bledy = [f"{b['portal']}: {b['blad']}" for b in
             db.execute("SELECT portal, blad FROM skany WHERE start=? AND blad IS NOT NULL", (r[0],))]
    return r[0], bledy


def statystyki(db):
    jeden = lambda sql, *a: db.execute(sql, a).fetchone()[0]
    return {
        "ofert_aktywnych": jeden("SELECT COUNT(*) FROM oferty WHERE aktywna=1"),
        "ofert_wygaslych": jeden("SELECT COUNT(*) FROM oferty WHERE aktywna=0"),
        "ogloszen": jeden("SELECT COUNT(*) FROM ogloszenia"),
        "na_wielu_portalach": jeden("SELECT COUNT(*) FROM ogloszenia "
                                    "WHERE json_array_length(portale) > 1"),
    }
