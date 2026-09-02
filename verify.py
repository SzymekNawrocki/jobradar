"""Weryfikator kandydatow na zrodla.

Dla listy {firma, ats, token} sprawdza, ile ofert firma ma lacznie i ile
z nich pasuje do Polski/Warszawy/zdalnych. Zostawiamy w sources.py tylko te,
ktore realnie zwracaja polskie oferty.

Uruchomienie:  py verify.py
"""

import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from providers import POBIERACZE
from radar import pasuje_lokalizacja

# Kandydaci zebrani z researchu (2026-08-31). Kategoria orientacyjna.
KANDYDACI = [
    {"firma": "Tenstorrent",   "ats": "greenhouse",    "token": "tenstorrent",  "kategoria": "hardware/embedded"},
    {"firma": "Waymo",         "ats": "greenhouse",    "token": "waymo",        "kategoria": "infra/linux"},
    {"firma": "Xebia CEE",     "ats": "greenhouse",    "token": "xebiacee",     "kategoria": "software"},
    {"firma": "Box",           "ats": "greenhouse",    "token": "boxinc",       "kategoria": "software"},
    {"firma": "Starburst",     "ats": "greenhouse",    "token": "starburst",    "kategoria": "data/backend"},
    {"firma": "EOS IT",        "ats": "greenhouse",    "token": "eositsolutions","kategoria": "it-support"},
    {"firma": "JetBrains",     "ats": "greenhouse_eu", "token": "jetbrains",    "kategoria": "software"},
    {"firma": "Palantir",      "ats": "lever",         "token": "palantir",     "kategoria": "software"},
    {"firma": "Nomagic",       "ats": "lever",         "token": "Nomagic",      "kategoria": "robotyka/ml"},
    {"firma": "Chooose",       "ats": "lever",         "token": "chooose",      "kategoria": "software"},
    {"firma": "Capital.com",   "ats": "lever",         "token": "capital",      "kategoria": "fintech"},
    {"firma": "SwingDev",      "ats": "lever",         "token": "swingdev",     "kategoria": "fullstack"},
    {"firma": "JetBridge",     "ats": "lever",         "token": "JetBridge",    "kategoria": "cloud/backend"},
    {"firma": "Bee Talents",   "ats": "lever",         "token": "bee-talents",  "kategoria": "rekrutacja-it"},
    {"firma": "AdColony",      "ats": "lever",         "token": "adcolony",     "kategoria": "software"},
    {"firma": "Scaleway",      "ats": "lever",         "token": "scaleway",     "kategoria": "cloud/devops"},
]


def main():
    print(f"{'FIRMA':<16} {'ATS':<14} {'WSZYST':>7} {'POLSKA':>7}   TOKEN")
    print("-" * 70)
    dzialajace = []
    for k in KANDYDACI:
        pobieracz = POBIERACZE.get(k["ats"])
        try:
            oferty = pobieracz(k)
            polskie = [o for o in oferty if pasuje_lokalizacja(o["lokacja"])]
            znak = "  <== bierzemy" if polskie else ""
            print(f"{k['firma']:<16} {k['ats']:<14} {len(oferty):>7} {len(polskie):>7}   {k['token']}{znak}")
            if polskie:
                dzialajace.append((k, len(polskie)))
        except Exception as e:  # noqa: BLE001
            print(f"{k['firma']:<16} {k['ats']:<14} {'ERR':>7} {'-':>7}   {k['token']}  ({e})")

    print("\n=== Firmy z polskimi ofertami (do sources.py) ===")
    for k, n in sorted(dzialajace, key=lambda x: -x[1]):
        print(f'    {{"firma": "{k["firma"]}", "ats": "{k["ats"]}", "token": "{k["token"]}", "kategoria": "{k["kategoria"]}"}},  # {n} PL')


if __name__ == "__main__":
    main()
