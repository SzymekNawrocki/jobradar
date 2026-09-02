"""JobRadar — radar NOWYCH warszawskich ofert IT ze stron karier firm.

Sens: pokazywac oferty, ktorych agregatory (jobhunt.pl) NIE maja — bo
bierzemy je u zrodla, ze stron karier firm (ATS), nie z innych portali.

Zasada nadrzedna: licza sie tylko NOWE oferty. Radar pamieta, co juz
widziales (seen.json), i pokazuje wylacznie to, co doszlo od ostatniego
razu — posortowane od najswiezszych.

Uruchomienie:  py radar.py
Zrodla dopisujesz w sources.py.
"""

import json
import sys
from datetime import datetime
from pathlib import Path

# Windowsowa konsola domyslnie tnie polskie znaki (cp1250) -> wymuszamy UTF-8
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import time

from sources import (SOURCES, LOKALIZACJE_OK, TYLKO_JUNIOR, MAKS_WIEK_DNI,
                     JUNIOR_SLOWA, SENIOR_SLOWA)
from providers import POBIERACZE

SEEN_FILE = Path(__file__).parent / "seen.json"
HTML_FILE = Path(__file__).parent / "oferty.html"


def poziom(tytul):
    """Zgaduje poziom stanowiska po tytule: 'junior' / 'senior' / 'mid'."""
    t = (tytul or "").lower()
    if any(s in t for s in JUNIOR_SLOWA):
        return "junior"
    if any(s in t for s in SENIOR_SLOWA):
        return "senior"
    return "mid"


# kraje, ktore od razu dyskwalifikuja oferte (np. "Remote, UK" nie jest dla nas)
OBCE_KRAJE = ["uk", "united kingdom", "us", "usa", "united states", "germany",
              "france", "spain", "india", "canada", "israel", "costa rica"]


def pasuje_lokalizacja(lokacja):
    l = (lokacja or "").lower()
    # jawnie polskie -> zawsze bierzemy
    if "warsaw" in l or "warszawa" in l or "poland" in l or "polska" in l:
        return True
    # zdalne bez wskazania obcego kraju -> tez bierzemy
    if ("remote" in l or "zdaln" in l) and not any(k in l for k in OBCE_KRAJE):
        return True
    return False


def zbierz_wszystkie():
    """Odpytuje kazde zrodlo z sources.py i skleja oferty w jedna liste.

    Blad jednego zrodla (padniety token, timeout) NIE wywala calosci —
    raportujemy go i lecimy dalej.
    """
    wszystkie = []
    for zrodlo in SOURCES:
        pobieracz = POBIERACZE.get(zrodlo["ats"])
        if pobieracz is None:
            print(f"[!] Nieznany ATS '{zrodlo['ats']}' dla {zrodlo['firma']} — pomijam")
            continue
        try:
            oferty = pobieracz(zrodlo)
            wszystkie.extend(oferty)
            print(f"[ok] {zrodlo['firma']}: {len(oferty)} ofert(y) z {zrodlo['ats']}")
        except Exception as e:  # noqa: BLE001 — chcemy zlapac wszystko, byle nie ubic calego radaru
            print(f"[!] {zrodlo['firma']} ({zrodlo['ats']}): blad — {e}")
    return wszystkie


def wczytaj_widziane():
    if SEEN_FILE.exists():
        return set(json.loads(SEEN_FILE.read_text(encoding="utf-8")))
    return set()


def zapisz_widziane(idki):
    SEEN_FILE.write_text(json.dumps(sorted(idki)), encoding="utf-8")


def _data(o):
    return datetime.fromtimestamp(o["data"]).strftime("%Y-%m-%d") if o["data"] else "?"


def zapisz_html(oferty, ile_nowych):
    """Zapisuje przegladalny raport HTML (jak jobhunt, tylko Twoj)."""
    naglowek = f"JobRadar — {len(oferty)} ofert ({ile_nowych} nowych)"
    wiersze = []
    for o in oferty:
        nowa = "🆕 " if o.get("nowa") else ""
        wiersze.append(f"""
        <a class="oferta {o['poziom']}" href="{o['url']}" target="_blank">
          <span class="lvl">{o['poziom']}</span>
          <span class="tytul">{nowa}{o['tytul']}</span>
          <span class="meta">{o['firma']} · {o['lokacja']} · {o['kategoria']} · {_data(o)}</span>
        </a>""")
    html = f"""<!doctype html><html lang="pl"><head><meta charset="utf-8">
<title>{naglowek}</title><style>
 body{{background:#0d1117;color:#e6edf3;font:14px/1.5 system-ui,sans-serif;margin:0;padding:24px}}
 h1{{font-size:18px;margin:0 0 16px}}
 .oferta{{display:grid;grid-template-columns:80px 1fr;gap:4px 12px;padding:12px 14px;
   margin:8px 0;background:#161b22;border:1px solid #30363d;border-radius:8px;
   text-decoration:none;color:inherit;border-left:4px solid #6e7681}}
 .oferta:hover{{border-color:#58a6ff}}
 .oferta.junior{{border-left-color:#3fb950}} .oferta.senior{{border-left-color:#f85149}}
 .oferta.mid{{border-left-color:#d29922}}
 .lvl{{grid-row:1/3;align-self:center;font-size:11px;text-transform:uppercase;
   color:#8b949e;letter-spacing:.5px}}
 .tytul{{font-weight:600}} .meta{{color:#8b949e;font-size:12px}}
</style></head><body><h1>{naglowek}</h1>{''.join(wiersze)}</body></html>"""
    HTML_FILE.write_text(html, encoding="utf-8")


def zbierz_i_przetworz(zapamietaj=True):
    """Pobiera, filtruje i oznacza oferty — wspolne dla terminala i frontendu.

    Zwraca liste ofert (posortowana od najswiezszych), kazda z polami
    'poziom' i 'nowa'. Jesli zapamietaj=True, aktualizuje seen.json
    (nastepnym razem te oferty nie beda juz 'nowe').
    """
    oferty = zbierz_wszystkie()

    # tylko warszawskie / polskie / zdalne
    nasze = [o for o in oferty if pasuje_lokalizacja(o["lokacja"])]

    # odetnij stare "wieczne" ogloszenia
    if MAKS_WIEK_DNI:
        prog = time.time() - MAKS_WIEK_DNI * 86400
        nasze = [o for o in nasze if o["data"] >= prog]

    # oznacz poziom; opcjonalnie zostaw tylko juniorskie
    for o in nasze:
        o["poziom"] = poziom(o["tytul"])
    if TYLKO_JUNIOR:
        nasze = [o for o in nasze if o["poziom"] == "junior"]

    widziane = wczytaj_widziane()
    for o in nasze:
        o["nowa"] = o["id"] not in widziane
    nasze.sort(key=lambda o: o["data"], reverse=True)

    if zapamietaj:
        zapisz_widziane(widziane | {o["id"] for o in nasze})
    return nasze


def main():
    print("Zbieram oferty ze stron karier...\n")
    nasze = zbierz_i_przetworz(zapamietaj=True)
    nowe = [o for o in nasze if o["nowa"]]

    print(f"\n{'='*50}")
    tryb = "TYLKO JUNIOR" if TYLKO_JUNIOR else "wszystkie poziomy"
    print(f"Ofert po filtrach ({tryb}): {len(nasze)}")
    print(f"{'='*50}\n")

    if not nowe:
        print("Brak NOWYCH ofert od ostatniego sprawdzenia.")
    else:
        print(f">>> {len(nowe)} NOWYCH ofert <<<\n")
        for o in nowe:
            print(f"[{_data(o)}] [{o['poziom']}] ({o['kategoria']}) {o['tytul']}")
            print(f"          {o['firma']} — {o['lokacja']}")
            print(f"          {o['url']}\n")

    # raport HTML pokazuje WSZYSTKIE nasze oferty (nowe oznaczone), do przegladania
    zapisz_html(nasze, len(nowe))
    print(f"Raport HTML: {HTML_FILE}")


if __name__ == "__main__":
    main()
