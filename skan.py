"""Skan portali IT -> baza jobradar.db. Tylko staz/junior, Warszawa albo zdalnie.

Uruchomienie:
    py skan.py

Portale leca rownolegle, kazdy osobno: jak jeden padnie (zmienil strone,
timeout), reszta dziala, a w raporcie widac, ktory. Wynik trafia do bazy
(baza.py): nowe oferty sa zapamietywane, duplikaty miedzy portalami
scalane, oferty zdjete z portali wygaszane.
"""

import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import baza
from portale import PORTALE


def skanuj_portal(nazwa):
    """Zwraca (nazwa, oferty, blad, sekundy) — nigdy nie rzuca wyjatkiem."""
    start = time.time()
    try:
        return nazwa, PORTALE[nazwa](), None, time.time() - start
    except Exception as e:  # noqa: BLE001 — jeden portal nie moze ubic skanu
        return nazwa, [], f"{type(e).__name__}: {e}", time.time() - start


def skanuj():
    with ThreadPoolExecutor(max_workers=len(PORTALE)) as pula:
        return list(pula.map(skanuj_portal, PORTALE))


def skanuj_i_zapisz(db):
    """Skan + zapis do bazy. Zwraca (start, wyniki, nowe) — uzywa tez app.py."""
    start = int(time.time())
    wyniki = skanuj()
    return start, wyniki, baza.zapisz_skan(db, wyniki, teraz=start)


def _widelki(o):
    if not (o["wid_od"] or o["wid_do"]):
        return ""
    k = lambda x: f"{round(x / 1000)}k" if x else "?"
    return f" · {k(o['wid_od'])}–{k(o['wid_do'])}"


def main():
    print("Skanuję portale (staż/junior, Warszawa + zdalne)...\n")
    db = baza.polacz()
    start, wyniki, nowe = skanuj_i_zapisz(db)

    for nazwa, oferty, blad, sek in wyniki:
        if blad:
            print(f"  ⚠ {nazwa:<9} BŁĄD po {sek:.0f}s — {blad}")
        else:
            print(f"  ✓ {nazwa:<9} {len(oferty):>4} ofert, {nowe[nazwa]:>4} nowych  ({sek:.0f}s)")

    s = baza.statystyki(db)
    print(f"\nW bazie: {s['ogloszen']} ogłoszeń po scaleniu "
          f"({s['ofert_aktywnych']} ofert, {s['na_wielu_portalach']} na kilku portalach, "
          f"{s['ofert_wygaslych']} wygasłych)")

    swieze = db.execute("SELECT * FROM ogloszenia WHERE pierwszy_raz = ? "
                        "ORDER BY data DESC LIMIT 15", (start,)).fetchall()
    print("\nNowe od ostatniego skanu (pokazuję do 15):")
    for o in swieze:
        portale = ", ".join(json.loads(o["portale"]))
        print(f"  {o['tytul']} — {o['firma']}{_widelki(o)}  [{portale}]")
        print(f"      {o['url']}")
    if not swieze:
        print("  (brak)")


if __name__ == "__main__":
    main()
