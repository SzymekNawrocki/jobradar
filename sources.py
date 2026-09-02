"""Kuratorska lista zrodel — SERCE projektu.

To NIE jest kolejny agregator. Zbieramy oferty ze stron karier firm
(systemy ATS z otwartym API JSON), ktorych agregatory typu jobhunt.pl
NIE maja — bo firma wrzuca oferte u siebie, zanim (albo zamiast) zaplaci
za wystawienie jej na Pracuj/LinkedIn.

Kazdy wpis: nazwa firmy, typ ATS, token (identyfikator firmy w tym ATS),
kategoria. Rozbudowuj te liste — to jest praca, ktora daje wartosc.

Trzy wspierane ATS-y z otwartym API (bez klucza, bez blokad):
  greenhouse      -> boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true
  lever           -> api.lever.co/v0/postings/{token}?mode=json
  smartrecruiters -> api.smartrecruiters.com/v1/companies/{token}/postings

Jak znalezc token firmy:
  - Wejdz na strone "Kariera" firmy, kliknij ofere.
  - Jesli URL to job-boards.greenhouse.io/NAZWA/... -> ats="greenhouse", token="NAZWA"
  - Jesli jobs.lever.co/NAZWA/...                   -> ats="lever", token="NAZWA"
  - Jesli jobs.smartrecruiters.com/NAZWA/...        -> ats="smartrecruiters", token="NAZWA"
"""

SOURCES = [
    # --- zweryfikowane na zywo (2026-08-31): zwracaja realne polskie oferty ---
    {"firma": "Xebia CEE",     "ats": "greenhouse", "token": "xebiacee",       "kategoria": "software"},
    {"firma": "Box",           "ats": "greenhouse", "token": "boxinc",         "kategoria": "software"},
    {"firma": "Capital.com",   "ats": "lever",      "token": "capital",        "kategoria": "fintech"},
    {"firma": "Waymo",         "ats": "greenhouse", "token": "waymo",          "kategoria": "infra/linux"},
    {"firma": "SwingDev",      "ats": "lever",      "token": "swingdev",       "kategoria": "fullstack"},
    {"firma": "Bee Talents",   "ats": "lever",      "token": "bee-talents",    "kategoria": "rekrutacja-it"},
    {"firma": "Nomagic",       "ats": "lever",      "token": "Nomagic",        "kategoria": "robotyka/ml"},
    {"firma": "Tenstorrent",   "ats": "greenhouse", "token": "tenstorrent",    "kategoria": "hardware/embedded"},
    {"firma": "Starburst",     "ats": "greenhouse", "token": "starburst",      "kategoria": "data/backend"},
    {"firma": "Chooose",       "ats": "lever",      "token": "chooose",        "kategoria": "software"},
    {"firma": "EOS IT",        "ats": "greenhouse", "token": "eositsolutions", "kategoria": "it-support"},
    {"firma": "JetBridge",     "ats": "lever",      "token": "JetBridge",      "kategoria": "cloud/backend"},
    {"firma": "Palantir",      "ats": "lever",      "token": "palantir",       "kategoria": "software"},
    {"firma": "Scaleway",      "ats": "lever",      "token": "scaleway",       "kategoria": "cloud/devops"},
    {"firma": "Torq",          "ats": "greenhouse", "token": "torq",           "kategoria": "cybersec"},
    {"firma": "Focal Systems", "ats": "greenhouse", "token": "focalsystems",   "kategoria": "web/backend"},

    # --- DOPISUJ TUTAJ (najpierw sprawdz w verify.py, czy ma polskie oferty) ---
    # Jak znalezc token: patrz naglowek tego pliku.
    # zbrojeniowka/panstwowka (WB, PGZ, PIT-RADWAR, cyber.mil.pl) zwykle NIE maja
    # otwartego ATS -> beda osobnym modulem (przegladarka/HTML), nie tutaj.
]

# Odcinaj oferty starsze niz tyle dni (0 = bez limitu). Tnie "wieczne"
# ogloszenia typu "General Application" z 2021 roku — licza sie swieze.
MAKS_WIEK_DNI = 45

# Pokazywac tylko oferty juniorskie? True = filtruj po tytule (junior/intern/
# mlodszy/trainee/entry...). False = pokaz wszystko, ale oznacz poziom.
TYLKO_JUNIOR = False

# Slowa w tytule -> poziom junior (do oznaczania i filtrowania)
JUNIOR_SLOWA = ["junior", "intern", "internship", "entry", "trainee", "graduate",
                "mlodszy", "młodszy", "praktykant", "praktyki", "stażyst", "stazyst",
                "associate", "apprentice"]
SENIOR_SLOWA = ["senior", "staff", "principal", "lead", "head", "director",
                "expert", "manager", "vp", "chief"]

# Slowa-klucze lokalizacji: oferta jest "nasza", jesli jej lokalizacja
# zawiera ktores z tych (ignorujac wielkosc liter). "remote" zostawiamy,
# bo zdalna z Polski tez sie liczy — mozesz je usunac, jak chcesz tylko Warszawe.
LOKALIZACJE_OK = ["warsaw", "warszawa", "poland", "polska", "remote", "zdaln"]
