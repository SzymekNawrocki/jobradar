# JobRadar

Lokalny zamiennik **jobhunt.pl** — świeże oferty IT (Warszawa + zdalne) z portali
i ze stron karier firm, w jednym miejscu.

## Skan portali (krok 1)

```bash
py skan.py            # pełny skan: wszystkie strony (~1,5 min, ~16 tys. ofert)
py skan.py --szybki   # tylko najnowsze strony każdego portalu (~5 s)
```

Wynik: `oferty.json` (w kroku 2 zastąpi go baza SQLite).

| Portal | Skąd bierzemy | Data publ. | Wygasa | Widełki |
|---|---|---|---|---|
| JustJoin.it | `justjoin.it/api/candidate-api/offers` (JSON) | ✅ | ✅ | ~50% |
| NoFluffJobs | `nofluffjobs.com/api/search/posting` (POST, JSON) | ✅ | — | ~98% |
| Pracuj.pl (IT) | `it.pracuj.pl`, JSON w stronie (`__NEXT_DATA__`) | ✅ | ✅ | ~45% |
| theprotocol.it | `__NEXT_DATA__` | ✅ | — | ~45% |
| Bulldogjob | `__NEXT_DATA__` | — | — | ~27% |

Każdy portal działa osobno — jak jeden zmieni stronę, reszta leci dalej, a skan
pokaże `⚠ portal BŁĄD`. Wtedy: zapisz nową odpowiedź jako fixture w
`tests/fixtury/`, popraw `parsuj_<portal>` w `portale.py`, aż przejdą testy:

```bash
py -m unittest -v
```

Wspólny format oferty (poziomy, tryby pracy, umowy, widełki w PLN/mies., stack)
jest opisany na górze `portale.py`.

---

## Radar stron karier firm (stara część)
## Po co to istnieje

jobhunt.pl agreguje inne portale (Pracuj, LinkedIn, JustJoin...) i odświeża co ~godzinę.
Firmy cross-postują te same oferty na wiele portali, więc agregatory się nakładają.

JobRadar bierze oferty **u źródła** — wprost ze stron karier firm (systemy ATS z otwartym
API). Taka oferta jest tam **pierwsza**, czasem **wyłącznie**, i pojawia się u nas, zanim
(albo bez tego, żeby) trafi na jakikolwiek agregator.

Zasada nadrzędna: **liczą się tylko NOWE oferty.** Radar pamięta, co już widziałeś
(`seen.json`), i pokazuje wyłącznie to, co doszło od ostatniego uruchomienia — od
najświeższych.

## Uruchomienie

```bash
py radar.py
```

Wypisze nowe oferty w terminalu i wygeneruje **`oferty.html`** — przeglądalny raport
(otwórz w przeglądarce), z kolorowym oznaczeniem poziomu (🟢 junior / 🟡 mid / 🔴 senior)
i znacznikiem 🆕 przy nowościach.

## Pliki

| Plik | Rola |
|---|---|
| `portale.py` | Portale (JustJoin, NoFluff, Pracuj, theprotocol, Bulldog) → wspólny format. |
| `skan.py` | Skan wszystkich portali równolegle → `oferty.json`. |
| `sources.py` | **Serce projektu** — lista firm (ATS + token + kategoria) i ustawienia filtrów. Tu dopisujesz nowe źródła. |
| `providers.py` | Łączy się z Greenhouse / Lever / SmartRecruiters i sprowadza różne formaty do jednego. |
| `radar.py` | Zbiera wszystko, filtruje (lokalizacja, wiek, poziom), wykrywa nowości, sortuje, drukuje + HTML. |
| `verify.py` | Sprawdza listę kandydatów: ile mają polskich ofert. Odpal przed dodaniem firmy do `sources.py`. |
| `seen.json` | Pamięć widzianych ofert (auto). |
| `oferty.html` | Wygenerowany raport (auto). |

## Ustawienia (w `sources.py`)

- `MAKS_WIEK_DNI` — odcinaj oferty starsze niż N dni (tnie „wieczne" ogłoszenia).
- `TYLKO_JUNIOR` — `True`, żeby pokazywać wyłącznie juniorskie.
- `LOKALIZACJE_OK` — słowa lokalizacji, które przepuszczamy.

## Jak dodać firmę

1. Wejdź na stronę „Kariera" firmy, otwórz dowolną ofertę, spójrz na URL:
   - `job-boards.greenhouse.io/NAZWA/...` → `"ats": "greenhouse", "token": "NAZWA"`
   - `jobs.lever.co/NAZWA/...` → `"ats": "lever", "token": "NAZWA"`
   - `jobs.smartrecruiters.com/NAZWA/...` → `"ats": "smartrecruiters", "token": "NAZWA"`
2. Dopisz kandydata w `verify.py` i odpal `py verify.py` — jeśli ma polskie oferty, dodaj do `sources.py`.

## Co dalej (pomysły)

- **Zbrojeniówka / państwówka** (WB, PGZ, PIT-RADWAR, cyber.mil.pl) — zwykle **nie mają**
  otwartego ATS. To osobny moduł na Playwright/przeglądarkę, nie na to API.
- Powiadomienia (mail / systemowe), harmonogram (uruchamiaj sam co godzinę).
