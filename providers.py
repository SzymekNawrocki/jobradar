"""Pobieranie ofert z roznych ATS-ow i sprowadzanie ich do jednego formatu.

Kazdy ATS zwraca inny ksztalt JSON. Tutaj kazda funkcja tlumaczy ten
konkretny ksztalt na WSPOLNY slownik oferty, ktory rozumie radar:

    {
      "id":       unikalny identyfikator (do wykrywania nowosci),
      "tytul":    nazwa stanowiska,
      "firma":    nazwa firmy,
      "lokacja":  miasto / kraj,
      "url":      link do aplikowania,
      "data":     unix timestamp publikacji (do sortowania po swiezosci),
      "kategoria": z sources.py,
    }
"""

import json
import urllib.request
from datetime import datetime, timezone


def _pobierz_json(url):
    """Pobiera i parsuje JSON. Udajemy przegladarke naglowkiem User-Agent."""
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 JobRadar"})
    with urllib.request.urlopen(req, timeout=25) as resp:
        return json.load(resp)


def _iso_na_ts(tekst):
    """Zamienia date ISO (np. '2026-08-30T10:00:00Z') na unix timestamp."""
    if not tekst:
        return 0
    try:
        tekst = tekst.replace("Z", "+00:00")
        return int(datetime.fromisoformat(tekst).timestamp())
    except ValueError:
        return 0


def greenhouse(zrodlo, host="boards-api.greenhouse.io"):
    url = f"https://{host}/v1/boards/{zrodlo['token']}/jobs?content=true"
    dane = _pobierz_json(url)
    oferty = []
    for j in dane.get("jobs", []):
        oferty.append({
            "id": f"gh-{j['id']}",
            "tytul": j.get("title", ""),
            "firma": zrodlo["firma"],
            "lokacja": (j.get("location") or {}).get("name", ""),
            "url": j.get("absolute_url", ""),
            "data": _iso_na_ts(j.get("updated_at") or j.get("first_published")),
            "kategoria": zrodlo["kategoria"],
        })
    return oferty


def greenhouse_eu(zrodlo):
    # niektore firmy (np. JetBrains) siedza na europejskim podzie Greenhouse
    return greenhouse(zrodlo, host="boards-api.eu.greenhouse.io")


def lever(zrodlo):
    url = f"https://api.lever.co/v0/postings/{zrodlo['token']}?mode=json"
    dane = _pobierz_json(url)
    oferty = []
    for j in dane:
        # createdAt w Leverze to milisekundy
        ts = int(j.get("createdAt", 0) / 1000) if j.get("createdAt") else 0
        oferty.append({
            "id": f"lv-{j.get('id', '')}",
            "tytul": j.get("text", ""),
            "firma": zrodlo["firma"],
            "lokacja": (j.get("categories") or {}).get("location", ""),
            "url": j.get("hostedUrl", ""),
            "data": ts,
            "kategoria": zrodlo["kategoria"],
        })
    return oferty


def smartrecruiters(zrodlo):
    url = f"https://api.smartrecruiters.com/v1/companies/{zrodlo['token']}/postings?limit=100"
    dane = _pobierz_json(url)
    oferty = []
    for j in dane.get("content", []):
        loc = j.get("location") or {}
        miasto = ", ".join(x for x in [loc.get("city"), loc.get("country")] if x)
        oferty.append({
            "id": f"sr-{j.get('id', '')}",
            "tytul": j.get("name", ""),
            "firma": zrodlo["firma"],
            "lokacja": miasto,
            "url": (j.get("ref") or ""),
            "data": _iso_na_ts(j.get("releasedDate")),
            "kategoria": zrodlo["kategoria"],
        })
    return oferty


# mapowanie nazwy ATS -> funkcja
POBIERACZE = {
    "greenhouse": greenhouse,
    "greenhouse_eu": greenhouse_eu,
    "lever": lever,
    "smartrecruiters": smartrecruiters,
}
