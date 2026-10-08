"""Pobieranie ofert z portali IT (to, co robil jobhunt.pl).

Zakres: TYLKO entry level (staz / junior) w Warszawie albo zdalnie.
Poziom filtruje sam portal (parametr w URL/API), wiec sciagamy kilkaset
ofert zamiast kilkunastu tysiecy — caly skan to kilkanascie zapytan.
Lokalnie i tak dosiewamy (_dla_mnie), bo "junior" na portalu potrafi
zlapac oferty "mid/senior" z dopiskiem junior w innym polu.

Kazdy portal ma dwie funkcje:

    parsuj_<portal>(dane) -> lista ofert   (czysta, bez sieci — testowana)
    pobierz_<portal>()    -> lista         (siec + paginacja)

Wspolny format oferty:

    {
      "id":       "jj-...", "nf-...", "pr-...", "tp-...", "bd-...", "sj-...", "li-..."
      "portal":   "justjoin" / "nofluff" / "pracuj" / "protocol" / "bulldog"
                  / "solid" / "linkedin",
      "tytul", "firma", "url",
      "miasta":   ["Warszawa", ...],
      "lokacja":  "Warszawa, Kraków" (to samo jako tekst),
      "data":     unix ts PIERWSZEJ publikacji, nie odswiezenia (0 = brak),
      "wygasa":   unix ts wygasniecia (0 = portal nie podaje),
      "poziomy":  podzbior ["staz", "junior", "mid", "senior", "lead"],
      "tryby":    podzbior ["zdalna", "hybrydowa", "biuro"] ([] = nie podano),
      "umowy":    podzbior ["b2b", "uop", "zlecenie", "staz", "inna"],
      "wid_od", "wid_do": PLN / miesiac (int) albo None,
      "stack":    ["Python", "React", ...],
      "kategoria": "backend" itp. albo "",
    }

Zrodla danych (zweryfikowane 2026-10-08):
  justjoin  -> justjoin.it/api/candidate-api/offers (JSON, kursor)
  nofluff   -> nofluffjobs.com/api/search/posting (POST, JSON, pageSize)
  pracuj    -> it.pracuj.pl, JSON wbudowany w strone (__NEXT_DATA__)
  protocol  -> theprotocol.it, __NEXT_DATA__
  bulldog   -> bulldogjob.pl, __NEXT_DATA__ (data tylko na stronie oferty)
  solid     -> solid.jobs/public-api/offers (feed dla agregatorow, JSON)
  linkedin  -> linkedin.com/jobs-guest (HTML kart, bez logowania; tylko Warszawa)

Uwaga na daty: JustJoin i Pracuj podaja tez date ODSWIEZENIA (platny "bump"),
przez ktora miesieczna oferta wyglada na dzisiejsza. Bierzemy zawsze pierwsza
publikacje — liczy sie, jak dawno oferta naprawde wisi.
"""

import gzip
import html
import json
import math
import re
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/129.0 Safari/537.36")

# przerwa miedzy kolejnymi stronami tego samego portalu — nie mlotkujemy
PRZERWA_S = 0.4

GODZIN_W_MIESIACU = 168
DNI_W_MIESIACU = 21
WIDELKI_SENSOWNE = (1000, 150000)  # PLN / miesiac — poza tym to blad w ogloszeniu


# --------------------------------------------------------------------------
# siec
# --------------------------------------------------------------------------

def _pobierz(url, dane=None, naglowki=None, proby=2):
    """GET (albo POST, gdy podasz dane) -> tekst. Gzip, zeby nie ciagnac MB.

    Jedna ponowna proba po chwili — portale czasem rzucaja pojedynczym 5xx.
    """
    h = {"User-Agent": UA, "Accept-Encoding": "gzip", **(naglowki or {})}
    for proba in range(proby):
        try:
            req = urllib.request.Request(url, data=dane, headers=h)
            with urllib.request.urlopen(req, timeout=40) as resp:
                surowe = resp.read()
                if resp.headers.get("Content-Encoding") == "gzip":
                    surowe = gzip.decompress(surowe)
                return surowe.decode("utf-8", "replace")
        except Exception:
            if proba == proby - 1:
                raise
            time.sleep(3)


def _next_data(html):
    """Wyciaga JSON, ktory strony na Next.js wstrzykuja w <script id=__NEXT_DATA__>."""
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
    if not m:
        raise ValueError("brak __NEXT_DATA__ — portal zmienil strone?")
    return json.loads(m.group(1))


# --------------------------------------------------------------------------
# normalizacja — wspolne dla wszystkich portali
# --------------------------------------------------------------------------

def _ts(tekst):
    """Data ISO -> unix ts. Bez strefy = UTC (tak podaje theprotocol)."""
    if not tekst:
        return 0
    try:
        t = tekst.replace("Z", "+00:00")
        if "+" not in t[10:]:
            t += "+00:00"
        # Python <3.11 nie lubi >6 cyfr ulamka sekundy (JustJoin daje 7)
        t = re.sub(r"(\.\d{6})\d+", r"\1", t)
        return int(datetime.fromisoformat(t).timestamp())
    except ValueError:
        return 0


# slowo z portalu (male litery) -> nasz poziom
POZIOMY = {
    "trainee": "staz", "intern": "staz", "internship": "staz",
    "junior": "junior", "assistant": "junior",
    "mid": "mid", "medium": "mid", "regular": "mid",
    "senior": "senior", "expert": "senior",
    "lead": "lead", "head": "lead", "manager": "lead", "c_level": "lead",
}

# Pracuj podaje opisowo, po polsku — szukamy fragmentu
POZIOMY_PRACUJ = [
    ("praktykant", "staz"), ("stażyst", "staz"),
    ("(junior)", "junior"), ("asystent", "junior"),
    ("(mid", "mid"), ("(senior)", "senior"), ("ekspert", "senior"),
    ("kierownik", "lead"), ("menedżer", "lead"), ("dyrektor", "lead"),
    ("prezes", "lead"),
]

KOLEJNOSC_POZIOMOW = ["staz", "junior", "mid", "senior", "lead"]


def _poziomy(slowa):
    wynik = {POZIOMY[s.lower()] for s in slowa if s and s.lower() in POZIOMY}
    return [p for p in KOLEJNOSC_POZIOMOW if p in wynik]


def _miesiecznie(kwota, jednostka):
    """Kwota w danej jednostce czasu -> PLN / miesiac."""
    if kwota is None:
        return None
    j = (jednostka or "month").lower()
    if j.startswith(("hour", "godz", "hr")):
        kwota *= GODZIN_W_MIESIACU
    elif j.startswith(("day", "dzie")):
        kwota *= DNI_W_MIESIACU
    elif j.startswith(("year", "rok")):
        kwota /= 12
    return int(round(kwota))


def _widelki(pary):
    """Z listy (od, do) w PLN/mies. robi jedne widelki: najnizsze od, najwyzsze do."""
    od = [p[0] for p in pary if p[0]]
    do = [p[1] for p in pary if p[1]]
    return (min(od) if od else None), (max(do) if do else None)


def _najwczesniej(*daty):
    """Najwczesniejsza niezerowa data (0 = brak)."""
    return min((d for d in daty if d), default=0)


def _uniq(lista):
    """Usuwa duplikaty, zachowujac kolejnosc."""
    return list(dict.fromkeys(x for x in lista if x))


def _oferta(**pola):
    o = {
        "id": "", "portal": "", "tytul": "", "firma": "", "url": "",
        "miasta": [], "data": 0, "wygasa": 0, "poziomy": [], "tryby": [],
        "umowy": [], "wid_od": None, "wid_do": None, "stack": [], "kategoria": "",
    }
    o.update(pola)
    # literowki pracodawcow (np. 3 276 000 zl/mies.) psulyby filtr zarobkow
    for k in ("wid_od", "wid_do"):
        if o[k] is not None and not WIDELKI_SENSOWNE[0] <= o[k] <= WIDELKI_SENSOWNE[1]:
            o[k] = None
    o["miasta"] = _uniq(o["miasta"])
    o["umowy"] = _uniq(o["umowy"])
    o["tryby"] = _uniq(o["tryby"])
    o["stack"] = _uniq(o["stack"])
    o["lokacja"] = ", ".join(o["miasta"])
    return o


def _dla_mnie(o):
    """Staz/junior w Warszawie albo zdalnie — reszta nas nie interesuje."""
    if not {"staz", "junior"} & set(o["poziomy"]):
        return False
    if "zdalna" in o["tryby"]:
        return True
    return any(m.lower() in ("warszawa", "warsaw") for m in o["miasta"])


# --------------------------------------------------------------------------
# JustJoin.it
# --------------------------------------------------------------------------

JJ_URL = ("https://justjoin.it/api/candidate-api/offers"
          "?orderBy=descending&sortBy=publishedAt&from={od}&itemsCount={ile}"
          "&experienceLevels=junior&experienceLevels=intern")
JJ_NA_STRONE = 1000

JJ_TRYBY = {"remote": "zdalna", "hybrid": "hybrydowa", "office": "biuro"}
JJ_UMOWY = {"b2b": "b2b", "permanent": "uop", "mandate_contract": "zlecenie",
            "internship": "staz"}


def parsuj_justjoin(dane):
    oferty = []
    for j in dane.get("data", []):
        miasta = [l.get("city") for l in j.get("locations") or []] or [j.get("city")]
        etaty = j.get("employmentTypes") or []
        # JJ daje kazde widelki w 5 walutach — bierzemy PLN (oryginal albo przeliczenie).
        # "from"/"to" sa juz miesieczne (stawka godzinowa siedzi w "fromPerUnit").
        pln = [(_miesiecznie(e.get("from"), "month"), _miesiecznie(e.get("to"), "month"))
               for e in etaty if e.get("currency", "").upper() == "PLN"]
        od, do = _widelki(pln)
        oferty.append(_oferta(
            id=f"jj-{j['guid']}",
            portal="justjoin",
            tytul=j.get("title", ""),
            firma=j.get("companyName", ""),
            url=f"https://justjoin.it/job-offer/{j['slug']}",
            miasta=miasta,
            # "publishedAt" to ODSWIEZENIE (platny bump — stara oferta wraca na gore
            # jako "dzisiejsza"); prawdziwa pierwsza publikacja to wczesniejsza z dwoch
            data=_najwczesniej(_ts(j.get("publishedAt")), _ts(j.get("lastPublishedAt"))),
            wygasa=_ts(j.get("expiredAt")),
            poziomy=_poziomy([j.get("experienceLevel")]),
            tryby=[JJ_TRYBY.get(j.get("workplaceType"), "")],
            umowy=[JJ_UMOWY.get(e.get("type"), "inna") for e in etaty],
            wid_od=od, wid_do=do,
            stack=[s.get("name") for s in j.get("requiredSkills") or []],
            kategoria=(j.get("category") or {}).get("key", ""),
        ))
    return oferty


def pobierz_justjoin():
    # Filtr "zdalne" w API nie dziala, wiec bierzemy cala Polske (staz+junior
    # to ~450 ofert, jedno zapytanie) i odsiewamy u siebie. Konczymy na
    # totalItems, nie na "next" — kursor za koncem zwraca HTTP 400.
    oferty, od = [], 0
    while True:
        dane = json.loads(_pobierz(JJ_URL.format(od=od, ile=JJ_NA_STRONE),
                                   naglowki={"Accept": "application/json",
                                             "Referer": "https://justjoin.it/"}))
        oferty.extend(parsuj_justjoin(dane))
        od += JJ_NA_STRONE
        if od >= ((dane.get("meta") or {}).get("totalItems") or 0):
            break
        time.sleep(PRZERWA_S)
    return [o for o in oferty if _dla_mnie(o)]


# --------------------------------------------------------------------------
# NoFluffJobs
# --------------------------------------------------------------------------

NF_URL = ("https://nofluffjobs.com/api/search/posting?salaryCurrency=PLN"
          "&salaryPeriod=month&region=pl&pageSize={ile}&page={strona}")
NF_POZIOMY = {"trainee": "staz", "junior": "junior", "mid": "mid",
              "senior": "senior", "expert": "senior", "lead": "lead", "head": "lead"}
NF_UMOWY = {"b2b": "b2b", "permanent": "uop", "zlecenie": "zlecenie",
            "intern": "staz"}


def parsuj_nofluff(dane):
    oferty = []
    for p in dane.get("postings", []):
        lok = p.get("location") or {}
        miasta = [pl.get("city") for pl in lok.get("places") or []
                  if pl.get("city") and pl.get("city") != "Remote"]
        tryby = []
        if lok.get("fullyRemote"):
            tryby.append("zdalna")
        elif lok.get("hybridDesc"):
            tryby.append("hybrydowa")
        s = p.get("salary") or {}
        od = do = None
        if s.get("currency", "PLN") == "PLN":
            od = _miesiecznie(s.get("from"), s.get("period"))
            do = _miesiecznie(s.get("to"), s.get("period"))
        kafelki = (p.get("tiles") or {}).get("values") or []
        oferty.append(_oferta(
            # ta sama oferta w kilku miastach ma rozne "id", ale wspolne "reference"
            id=f"nf-{p.get('reference') or p['id']}",
            portal="nofluff",
            tytul=p.get("title", ""),
            firma=p.get("name", ""),
            url=f"https://nofluffjobs.com/pl/job/{p['url']}",
            miasta=miasta,
            data=int((p.get("posted") or 0) / 1000),
            poziomy=[NF_POZIOMY[x.lower()] for x in p.get("seniority") or []
                     if x.lower() in NF_POZIOMY],
            tryby=tryby,
            umowy=[NF_UMOWY.get(s.get("type"), "inna")] if s else [],
            wid_od=od, wid_do=do,
            stack=[p.get("technology")] + [k["value"] for k in kafelki
                                           if k.get("type") == "requirement"],
            kategoria=p.get("category", ""),
        ))
    return oferty


def pobierz_nofluff():
    # API oddaje do ~2000 ofert na raz — Warszawa i zdalne to po jednym zapytaniu
    wynik = {}
    for miasto in ("warszawa", "remote"):
        strona = 1
        while True:
            kryteria = {"city": [miasto], "seniority": ["trainee", "junior"]}
            body = json.dumps({"criteriaSearch": kryteria, "page": strona}).encode()
            dane = json.loads(_pobierz(
                NF_URL.format(ile=2000, strona=strona), dane=body,
                naglowki={"Content-Type": "application/infiniteSearch+json"}))
            for o in parsuj_nofluff(dane):
                wynik.setdefault(o["id"], o)
            if strona >= (dane.get("totalPages") or 1):
                break
            strona += 1
            time.sleep(PRZERWA_S)
        time.sleep(PRZERWA_S)
    return [o for o in wynik.values() if _dla_mnie(o)]


# --------------------------------------------------------------------------
# Pracuj.pl (sekcja IT)
# --------------------------------------------------------------------------

# sc=0: od najnowszych; et=1,3,17: praktykant, asystent, junior
PR_URLE = [
    "https://it.pracuj.pl/praca/warszawa;wp?sc=0&et=1,3,17&pn={strona}",
    "https://it.pracuj.pl/praca?sc=0&et=1,3,17&wm=home-office&pn={strona}",  # zdalne, cala Polska
]
PR_TRYBY = {"praca zdalna": "zdalna", "praca hybrydowa": "hybrydowa",
            "praca stacjonarna": "biuro"}
PR_UMOWY = {"kontrakt b2b": "b2b", "umowa o pracę": "uop",
            "umowa zlecenie": "zlecenie", "umowa o staż / praktyki": "staz"}

# "18 900–22 470 zł netto (+ VAT) / mies." / "100–130 zł brutto / godz."
PR_KWOTA = re.compile(r"([\d\s\xa0]+?)(?:\s*[–-]\s*([\d\s\xa0]+?))?\s*zł.*?/\s*(mies|godz|dzie|rok)")


def _pracuj_widelki(tekst):
    m = PR_KWOTA.search(tekst or "")
    if not m:
        return None, None
    liczba = lambda s: int(re.sub(r"\D", "", s)) if s and re.sub(r"\D", "", s) else None
    od, do = liczba(m.group(1)), liczba(m.group(2))
    return _miesiecznie(od, m.group(3)), _miesiecznie(do or od, m.group(3))


def _pracuj_zapytanie(dane):
    """Glowna lista ofert siedzi w jednym z zapytan react-query (queryKey 'jobOffers')."""
    zapytania = dane["props"]["pageProps"]["dehydratedState"]["queries"]
    for z in zapytania:
        if z.get("queryKey", [None])[0] == "jobOffers":
            return z["state"]["data"]
    raise ValueError("brak zapytania jobOffers — portal zmienil strone?")


def parsuj_pracuj(dane):
    oferty = []
    for g in _pracuj_zapytanie(dane).get("groupedOffers", []):
        warianty = g.get("offers") or []
        miasta = [w.get("displayWorkplace", "").split(",")[0].strip() for w in warianty]
        # link: wersja warszawska, jesli jest — inaczej pierwsza
        url = next((w["offerAbsoluteUri"] for w in warianty
                    if w.get("displayWorkplace", "").startswith("Warszawa")),
                   warianty[0]["offerAbsoluteUri"] if warianty else "")
        poziomy = {p for opis in g.get("positionLevels") or []
                   for fraza, p in POZIOMY_PRACUJ if fraza in opis.lower()}
        od, do = _pracuj_widelki(g.get("salaryDisplayText"))
        oferty.append(_oferta(
            id=f"pr-{g['groupId']}",
            portal="pracuj",
            tytul=g.get("jobTitle", ""),
            firma=g.get("companyName", ""),
            url=url,
            miasta=miasta,
            # lastPublicated to odswiezenie — liczy sie pierwsza publikacja
            data=_ts(g.get("initialPublicated") or g.get("lastPublicated")),
            wygasa=_ts(g.get("expirationDate")),
            poziomy=[p for p in KOLEJNOSC_POZIOMOW if p in poziomy],
            tryby=[PR_TRYBY.get(t.lower(), "") for t in g.get("workModes") or []],
            umowy=[PR_UMOWY.get(u.lower(), "inna") for u in g.get("typesOfContract") or []],
            wid_od=od, wid_do=do,
            stack=g.get("technologies") or [],
        ))
    return oferty


def _pracuj_ile_stron(dane):
    d = _pracuj_zapytanie(dane)
    return math.ceil((d.get("groupedOffersTotalCount") or 0) / 50) or 1


def pobierz_pracuj():
    wynik = {}
    for wzor in PR_URLE:
        strona, ostatnia = 1, 1
        while True:
            dane = _next_data(_pobierz(wzor.format(strona=strona)))
            if strona == 1:
                ostatnia = _pracuj_ile_stron(dane)
            for o in parsuj_pracuj(dane):
                wynik.setdefault(o["id"], o)
            if strona >= ostatnia:
                break
            strona += 1
            time.sleep(PRZERWA_S)
    return [o for o in wynik.values() if _dla_mnie(o)]


# --------------------------------------------------------------------------
# theprotocol.it
# --------------------------------------------------------------------------

TP_URLE = [
    "https://theprotocol.it/filtry/trainee,assistant,junior;p/warszawa;wp?pageNumber={strona}",
    "https://theprotocol.it/filtry/trainee,assistant,junior;p/zdalna;rw?pageNumber={strona}",
]
TP_TRYBY = {"remote": "zdalna", "zdalna": "zdalna", "hybrid": "hybrydowa",
            "hybrydowa": "hybrydowa", "stacjonarna": "biuro", "full office": "biuro"}
# id ze slownika "contracts" w danych strony
TP_UMOWY = {3: "b2b", 0: "uop", 2: "zlecenie", 7: "staz"}


def parsuj_protocol(dane):
    odp = dane["props"]["pageProps"]["offersResponse"]
    oferty = []
    for o in odp.get("offers", []):
        umowy, pary = [], []
        for u in o.get("typesOfContracts") or []:
            umowy.append(TP_UMOWY.get(u.get("id"), "inna"))
            s = u.get("salary")
            if s and s.get("currencySymbol") == "zł":
                jedn = "hour" if s.get("timeUnitId") == 1 else "month"
                pary.append((_miesiecznie(s.get("from"), jedn), _miesiecznie(s.get("to"), jedn)))
        od, do = _widelki(pary)
        oferty.append(_oferta(
            id=f"tp-{o.get('groupId') or o['id']}",
            portal="protocol",
            tytul=o.get("title", ""),
            firma=o.get("employer", ""),
            url=f"https://theprotocol.it/szczegoly/praca/{o['offerUrlName']}",
            miasta=[w.get("city") for w in o.get("workplace") or []],
            data=_ts(o.get("publicationDateUtc")),
            poziomy=_poziomy([p.get("value") for p in o.get("positionLevels") or []]),
            tryby=[TP_TRYBY.get(t.lower(), "") for t in o.get("workModes") or []],
            umowy=umowy,
            wid_od=od, wid_do=do,
            stack=o.get("technologies") or [],
        ))
    return oferty


def pobierz_protocol():
    wynik = {}
    for wzor in TP_URLE:
        strona = 1
        while True:
            dane = _next_data(_pobierz(wzor.format(strona=strona)))
            for o in parsuj_protocol(dane):
                wynik.setdefault(o["id"], o)
            ostatnia = dane["props"]["pageProps"]["offersResponse"]["page"]["count"]
            if strona >= ostatnia:
                break
            strona += 1
            time.sleep(PRZERWA_S)
    return [o for o in wynik.values() if _dla_mnie(o)]


# --------------------------------------------------------------------------
# Bulldogjob
# --------------------------------------------------------------------------

BD_URLE = [
    "https://bulldogjob.pl/companies/jobs/s/city,Warszawa/experienceLevel,junior,intern/page,{strona}",
    "https://bulldogjob.pl/companies/jobs/s/city,Remote/experienceLevel,junior,intern/page,{strona}",
]
BD_NA_STRONE = 50


def parsuj_bulldog(dane):
    oferty = []
    for j in dane["props"]["pageProps"].get("jobs", []):
        tryby = []
        procent = (j.get("environment") or {}).get("remotePossible")
        if j.get("remote") or procent == 100:
            tryby.append("zdalna")
        elif procent:
            tryby.append("hybrydowa")
        elif procent == 0:
            tryby.append("biuro")
        umowy = [u for u, flaga in (("b2b", j.get("contractB2b")),
                                    ("uop", j.get("contractEmployment")),
                                    ("inna", j.get("contractOther"))) if flaga]
        od = do = None
        s = j.get("denominatedSalaryLong") or {}
        if s.get("money") and s.get("currency") == "PLN":
            liczby = [int(re.sub(r"\D", "", x)) for x in s["money"].split("-")
                      if re.sub(r"\D", "", x)]
            if liczby:
                # Bulldog nie mowi, czy to stawka godzinowa — male kwoty to godzinowe
                jedn = "hour" if max(liczby) < 1000 else "month"
                od, do = _miesiecznie(min(liczby), jedn), _miesiecznie(max(liczby), jedn)
        oferty.append(_oferta(
            id=f"bd-{j['id'].split('-')[0]}",
            portal="bulldog",
            tytul=j.get("position", ""),
            firma=(j.get("company") or {}).get("name", ""),
            url=f"https://bulldogjob.pl/companies/jobs/{j['id']}",
            miasta=[m.strip() for m in (j.get("city") or "").split(",")],
            poziomy=_poziomy([j.get("experienceLevel")]),
            tryby=tryby,
            umowy=umowy,
            wid_od=od, wid_do=do,
            stack=j.get("technologyTags") or [],
        ))
    return oferty


def parsuj_bulldog_szczegoly(dane):
    """Strona pojedynczej oferty -> (publikacja, wygasa). Lista ich nie podaje."""
    job = ((dane["props"]["pageProps"].get("data") or {}).get("job")) or {}
    return _ts(job.get("publishedAt")), _ts(job.get("endsAt"))


def _bulldog_daty(o):
    try:
        o["data"], o["wygasa"] = parsuj_bulldog_szczegoly(_next_data(_pobierz(o["url"])))
    except Exception:
        pass  # brak daty to nie powod, zeby zgubic oferte


def pobierz_bulldog():
    wynik = {}
    for wzor in BD_URLE:
        strona = 1
        while True:
            dane = _next_data(_pobierz(wzor.format(strona=strona)))
            for o in parsuj_bulldog(dane):
                wynik.setdefault(o["id"], o)
            ostatnia = math.ceil((dane["props"]["pageProps"].get("totalCount") or 0) / BD_NA_STRONE)
            if strona >= ostatnia:
                break
            strona += 1
            time.sleep(PRZERWA_S)
    oferty = [o for o in wynik.values() if _dla_mnie(o)]
    # daty publikacji sa tylko na stronach ofert — ~25 zapytan, 4 naraz
    with ThreadPoolExecutor(max_workers=4) as pula:
        list(pula.map(_bulldog_daty, oferty))
    return oferty


# --------------------------------------------------------------------------
# SolidJobs
# --------------------------------------------------------------------------

# Publiczny feed dla agregatorow (z niego korzystal jobhunt). Filtrow nie ma,
# ale jest posortowany od najnowszych: pierwsze 500 ofert to ~2 tygodnie,
# a starsze nas nie obchodza. Jedno zapytanie, ~0,8 MB.
SJ_URL = "https://solid.jobs/public-api/offers?campaign=jobradar&pageSize=500&pageIndex=0"
SJ_UMOWY = {"B2B": "b2b", "UoP": "uop", "UZ": "zlecenie", "Staż": "staz"}


def parsuj_solid(dane):
    oferty = []
    for j in dane.get("jobs", []):
        if j.get("division") != "IT":  # feed ma tez sprzedaz, finanse, HR...
            continue
        s = j.get("salary") or {}
        od = do = None
        if s.get("currency") == "PLN":
            od = _miesiecznie(s.get("from"), s.get("period"))
            do = _miesiecznie(s.get("to"), s.get("period"))
        tryby = (["zdalna"] if j.get("isRemote") else
                 ["hybrydowa"] if j.get("isHybrid") else ["biuro"])
        oferty.append(_oferta(
            id=f"sj-{j['jobOfferKey']}",
            portal="solid",
            tytul=j.get("title", ""),
            firma=j.get("company", ""),
            url=j.get("url", ""),
            miasta=j.get("locations") or [],
            data=_ts(j.get("validFrom")),
            wygasa=_ts(j.get("validTo")),
            poziomy=_poziomy([j.get("experienceLevel")]),
            tryby=tryby,
            umowy=[SJ_UMOWY.get(s.get("employmentType"), "inna")] if s else [],
            wid_od=od, wid_do=do,
            stack=[k.get("name") for k in j.get("skills") or []],
            kategoria=j.get("category", ""),
        ))
    return oferty


def pobierz_solid():
    dane = json.loads(_pobierz(SJ_URL, naglowki={"Accept": "application/json"}))
    return [o for o in parsuj_solid(dane) if _dla_mnie(o)]


# --------------------------------------------------------------------------
# LinkedIn (publiczna wyszukiwarka, bez logowania)
# --------------------------------------------------------------------------

# Tu sa programy stazowe korporacji (Google, Revolut, Intel...), ktorych nie
# ma na portalach IT. Filtry poziomu, branzy i "zdalnie" LinkedIn bez
# logowania ignoruje, wiec: tylko Warszawa, ostatni tydzien, a poziom i IT
# rozpoznajemy po tytule. "praktyki IT" (wyszukiwanie jest rozmyte) lapie
# ~95% stazy/juniorow IT w Warszawie — sprawdzone na 12 zapytaniach.
# Wiecej zapytan = ryzyko HTTP 429 (zlapalismy je po ~300 z rzedu).
LI_URL = ("https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
          "?keywords={fraza}&location=Warszawa&f_TPR=r604800&start={od}")
LI_FRAZY = ["praktyki IT", "software intern"]
LI_NA_STRONE = 10
LI_MAKS_STRON = 40
LI_PRZERWA_S = 1.0

LI_STAZ = re.compile(r"\b(intern|internship|sta[żz]\w*|praktyk\w*|trainee)\b", re.I)
LI_JUNIOR = re.compile(r"\b(junior|jr|m[łl]odsz\w*|graduate|entry[- ]level|absolwent\w*)\b", re.I)
LI_NIE = re.compile(r"\b(senior|lead|principal|staff|head|manager|kierownik\w*|dyrektor\w*)\b", re.I)
LI_IT = re.compile(
    r"develop|programi|software|oprogramowan|tester|\bqa\b|test automation|devops"
    r"|\bsre\b|site reliability|front-?end|back-?end|full[- ]?stack|python|java"
    r"|\.net|c\+\+|c#|golang|react|angular|node|\bit\b|cloud|security|cyber"
    r"|\bsoc\b|sysadmin|system administrator|administrator system|help ?desk"
    r"|service desk|data (analyst|engineer|scien)|analytics engineer|analityk danych"
    r"|in[żz]ynier danych|machine learning|\bml\b|\bai\b|\bllm|\bweb|mobile|android"
    r"|\bios\b|abap|\bsap\b|salesforce|\bsql\b|\bbi\b|power platform|\brpa\b"
    r"|\bux\b|\bui\b", re.I)


def _linkedin_poziomy(tytul):
    if LI_NIE.search(tytul):
        return []
    return [p for p, wzor in (("staz", LI_STAZ), ("junior", LI_JUNIOR)) if wzor.search(tytul)]


def parsuj_linkedin(strona):
    """Strona wynikow (HTML, 10 kart) -> oferty staz/junior IT. Reszte pomija."""
    oferty = []
    for karta in strona.split("<li>")[1:]:
        id_ = re.search(r"jobPosting:(\d+)", karta)
        tytul = re.search(r'base-search-card__title">\s*(.*?)\s*</h3>', karta, re.S)
        firma = re.search(r'base-search-card__subtitle">.*?>\s*(.*?)\s*</a>', karta, re.S)
        miejsce = re.search(r'job-search-card__location">\s*(.*?)\s*</span>', karta, re.S)
        data = re.search(r'<time[^>]*datetime="(\d{4}-\d\d-\d\d)"', karta)
        if not (id_ and tytul):
            continue
        tytul = html.unescape(tytul.group(1))
        poziomy = _linkedin_poziomy(tytul)
        if not poziomy or not LI_IT.search(tytul):
            continue
        miasto = miejsce.group(1).split(",")[0] if miejsce else ""
        oferty.append(_oferta(
            id=f"li-{id_.group(1)}",
            portal="linkedin",
            tytul=tytul,
            firma=html.unescape(firma.group(1)) if firma else "",
            url=f"https://www.linkedin.com/jobs/view/{id_.group(1)}",
            miasta=["Warszawa" if miasto == "Warsaw" else miasto],
            # sam dzien; przy ponownym wystawieniu oferty LinkedIn daje nowa date
            data=_ts(data.group(1) + "T00:00:00") if data else 0,
            poziomy=poziomy,
        ))
    return oferty


def pobierz_linkedin():
    wynik = {}
    for fraza in LI_FRAZY:
        for nr in range(LI_MAKS_STRON):
            strona = _pobierz(LI_URL.format(fraza=urllib.parse.quote(fraza),
                                            od=nr * LI_NA_STRONE))
            if "<li>" not in strona:  # koniec wynikow
                break
            for o in parsuj_linkedin(strona):
                # ta sama oferta bywa wystawiona kilka razy (rozne id) — zostaje
                # jedna, zawsze ta sama, zeby Twoj status przy niej nie skakal
                k = (o["tytul"].lower(), o["firma"].lower())
                if k not in wynik or o["id"] < wynik[k]["id"]:
                    wynik[k] = o
            time.sleep(LI_PRZERWA_S)
    return [o for o in wynik.values() if _dla_mnie(o)]


# nazwa portalu -> funkcja pobierajaca
PORTALE = {
    "justjoin": pobierz_justjoin,
    "nofluff": pobierz_nofluff,
    "pracuj": pobierz_pracuj,
    "protocol": pobierz_protocol,
    "bulldog": pobierz_bulldog,
    "solid": pobierz_solid,
    "linkedin": pobierz_linkedin,
}
