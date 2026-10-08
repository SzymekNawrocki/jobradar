"""Skan portali IT — krok 1 (zamiennik jobhunt.pl).

Uruchomienie:
    py skan.py            pelny skan (wszystkie strony, ~2-3 min)
    py skan.py --szybki   tylko najnowsze strony kazdego portalu (~20 s)

Portale leca rownolegle, kazdy osobno: jak jeden padnie (zmienil strone,
timeout), reszta dziala, a w raporcie widac, ktory. Wynik laduje w
oferty.json — w kroku 2 zastapi go baza SQLite.
"""

import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from portale import PORTALE

PLIK = Path(__file__).parent / "oferty.json"
STRONY_SZYBKI = 2


def skanuj_portal(nazwa, maks_stron):
    """Zwraca (nazwa, oferty, blad, sekundy) — nigdy nie rzuca wyjatkiem."""
    start = time.time()
    try:
        return nazwa, PORTALE[nazwa](maks_stron), None, time.time() - start
    except Exception as e:  # noqa: BLE001 — jeden portal nie moze ubic skanu
        return nazwa, [], f"{type(e).__name__}: {e}", time.time() - start


def skanuj(maks_stron=None):
    with ThreadPoolExecutor(max_workers=len(PORTALE)) as pula:
        return list(pula.map(lambda n: skanuj_portal(n, maks_stron), PORTALE))


def _widelki(o):
    if not (o["wid_od"] or o["wid_do"]):
        return ""
    k = lambda x: f"{round(x / 1000)}k" if x else "?"
    return f" · {k(o['wid_od'])}–{k(o['wid_do'])}"


def main():
    szybki = "--szybki" in sys.argv
    print(f"Skanuję portale ({'szybko: najnowsze strony' if szybki else 'pełny skan'})...\n")
    wyniki = skanuj(STRONY_SZYBKI if szybki else None)

    wszystkie = []
    for nazwa, oferty, blad, sek in wyniki:
        if blad:
            print(f"  ⚠ {nazwa:<9} BŁĄD po {sek:.0f}s — {blad}")
        else:
            print(f"  ✓ {nazwa:<9} {len(oferty):>5} ofert  ({sek:.0f}s)")
        wszystkie.extend(oferty)

    wszystkie.sort(key=lambda o: o["data"], reverse=True)
    PLIK.write_text(json.dumps(wszystkie, ensure_ascii=False), encoding="utf-8")
    print(f"\nRazem: {len(wszystkie)} ofert (Warszawa + zdalne) → {PLIK.name}")

    # podglad: najswiezsze juniorskie, zeby od razu bylo widac, ze dziala
    mlode = [o for o in wszystkie if {"staz", "junior"} & set(o["poziomy"])]
    print(f"\nNajświeższe junior/staż ({len(mlode)} łącznie):")
    for o in mlode[:12]:
        print(f"  [{o['portal']}] {o['tytul']} — {o['firma']}{_widelki(o)}")
        print(f"      {o['url']}")


if __name__ == "__main__":
    main()
