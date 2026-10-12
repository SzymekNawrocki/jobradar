# JobRadar

Lokalny zamiennik **jobhunt.pl**, zawężony do tego, czego szukam:
**staż / junior, Warszawa albo zdalnie**. Mid/senior nie są w ogóle pobierane.

## Użycie

```bash
py app.py       # strona na http://localhost:8010 + skan co 30 min, dopóki działa
py skan.py      # sam skan w terminalu (~30 s, ~550 ogłoszeń)
```

Albo skrót **JobRadar** na Pulpicie (zamknięcie jego okna wyłącza radar).

**Najważniejsza jest świeżość.** Strona domyślnie pokazuje oferty opublikowane
w ostatnim tygodniu (przełączniki: dziś / 3 dni / tydzień / wszystkie). Liczy się
data **pierwszej** publikacji, nie odświeżenia: JustJoin i Pracuj podają też datę
płatnego „podbicia”, przez którą miesięczna oferta wygląda na dzisiejszą. Przy
ofercie z kilku portali bierzemy najwcześniejszą datę.

Na stronie: lista od najświeższych, 🆕 przy tym, czego jeszcze nie widziałeś
(„✓ Przejrzane” zeruje), szukajka po tytule / firmie / technologiach (bez polskich
znaków też działa), przełączniki zdalnie / hybrydowo / biuro i przy każdej ofercie
„Zaaplikowałem” albo „Ukryj” — obie trafiają do osobnych zakładek i nie wracają.

Poziom filtruje sam portal (parametr w zapytaniu), więc cały skan to kilkanaście
zapytań zamiast tysięcy ofert. Lokalnie i tak dosiewamy staż/junior + Warszawa/zdalne.

| Portal | Skąd bierzemy | Filtr poziomu | Data publ. | Wygasa |
|---|---|---|---|---|
| JustJoin.it | `justjoin.it/api/candidate-api/offers` (JSON) | `experienceLevels=junior,intern` | ✅ | ✅ |
| NoFluffJobs | `nofluffjobs.com/api/search/posting` (POST) | `seniority: trainee, junior` | ✅ | — |
| Pracuj.pl (IT) | `it.pracuj.pl`, `__NEXT_DATA__` | `et=1,3,17` | ✅ | ✅ |
| theprotocol.it | `__NEXT_DATA__` | `trainee,assistant,junior;p` | ✅ | — |
| Bulldogjob | `__NEXT_DATA__` (+ strona oferty) | `experienceLevel,junior,intern` | ✅ | ✅ |
| SolidJobs | `solid.jobs/public-api/offers` (feed dla agregatorów) | lokalnie, `experienceLevel` | ✅ | ✅ |
| LinkedIn | `linkedin.com/jobs-guest` (HTML, bez logowania) | lokalnie, po tytule | dzień | — |
| Służba cywilna (KPRM) | `nabory.kprm.gov.pl` (HTML) | lokalnie, hierarchia stanowisk | — | ✅ |
| Strony firm (eRecruiter) | widget `skk.erecruiter.pl` (EXATEL, Grupa PGZ) | lokalnie, po tytule | część | — |

Wynik trafia do bazy **`jobradar.db`** (SQLite, `baza.py`):

- **pamięć** — każda oferta ma „pierwszy raz widziana”; skan pokazuje, ile doszło nowych,
- **duplikaty** — ta sama oferta z kilku portali to jedno ogłoszenie z kilkoma linkami
  (firma + tytuł bez dopisków typu „(k/m)”; max jedna oferta z portalu na ogłoszenie,
  a firmy outsourcingowe z wieloma „Tester manualny” rozdzielane po widełkach),
- **wygasanie** — oferty, których nie ma w skanie, zniknęły z portalu (z bezpiecznikiem:
  gdy portal nagle odda < połowy ofert, niczego nie wygaszamy).

Bulldog nie podaje daty publikacji na liście — dociągamy ją ze strony każdej oferty.

**SolidJobs** nie ma filtrów, ale feed jest posortowany od najnowszych — bierzemy
pierwsze 500 ofert (~2 tygodnie) i odsiewamy dział IT + staż/junior.

**LinkedIn** dokłada programy stażowe korporacji, których nie ma na portalach IT.
Bez logowania ignoruje filtry poziomu, branży i „zdalnie”, więc bierzemy **tylko
Warszawę z ostatniego tygodnia**, a poziom i „czy to IT” rozpoznajemy po tytule.
Fraza „praktyki IT” łapie ~95% takich ofert; więcej zapytań grozi blokadą (HTTP 429).

**Służba cywilna** (ministerstwa, urzędy, CBZC, sektorowe CSIRT-y) nie wystawia się
na portalach IT. Bierzemy Warszawę: branże „IT” i „informatyzacja” oraz frazy
„cyberbezpieczeństwo”, „teleinformaty…”, „informaty…”. Tytuły są ogólne („specjalista”),
więc o tym, czy to IT, decyduje też dział, a strona pokazuje go przy ofercie. Poziom
wynika z hierarchii: referent / młodszy → junior, specjalista → junior/mid, starszy,
główny, radca → odpada. Daty publikacji lista z filtrami nie podaje, więc liczy się
pierwszy raz widziana. Nabory z pierwszego skanu są tylko pod „wszystkie”.

**Strony firm** to widget eRecruitera, z którego korzysta wiele spółek skarbu państwa
i zbrojeniówka. Zbrojeniówka rzadko pisze poziom w tytule („Programista Java”), więc
tytuł bez poziomu = junior/mid, a odpadają starsi, architekci i kierownicy. Nowa firma:
w źródle jej strony „Kariera” znajdź `erecruiter.pl/Code.ashx?cfg=<32 znaki>` i dopisz
`(cfg, nazwa)` do `ER_FIRMY` w `portale.py`.

**📋 Aplikacje** to dziennik. „✓ Zaaplikowałem” przy ofercie zakłada w nim wpis
z kopią oferty (tytuł, firma, link, widełki, stack), który zostaje, gdy oferta zniknie
z portalu. Każdy wpis ma etap (wysłane → odpowiedź → rozmowa HR → zadanie → oferta /
odmowa / brak odpowiedzi, z historią zmian), notatki i kontakt zapisywane w locie oraz
datę następnego kroku. Domyślnie za tydzień od aplikacji; gdy minie, wpis dostaje
⏰ „czas na follow-up”, a licznik pojawia się w nawigacji. Aplikacje spoza radaru
(formularz WOC, nabór KPRM na papierze, polecenie) dodaje się ręcznie. Na górze
statystyki: ile odpowiedzi i rozmów na wysłane.

Obok są dwie zakładki do szukania kontaktów:

- **🏛️ Firmy i państwówka**: na górze to, co radar ma teraz z urzędów i stron firm
  (pogrupowane po pracodawcy), niżej katalog z `firmy.json` (cyber, wojsko i służby,
  zbrojeniówka, państwowe instytucje i spółki): strona kariery, praktyki, LinkedIn
  i oferty tej firmy z dowolnego portalu (dopasowanie po `aliasy`). Nową firmę dopisuje
  się w `firmy.json`, bez restartu.
- **👤 Rekruterzy**: wszystkie firmy z Twoich ofert, najpierw te, do których aplikowałeś
  (pora na wiadomość do rekrutera). Przy każdej: rekruterzy / HR, ludzie z IT (polecenie)
  i profil firmy na LinkedIn.

Przy każdej ofercie jest **👤 rekruterzy**: wyszukiwarka osób na LinkedIn
(rekruterzy / HR / talent acquisition tej firmy), otwierana na zalogowanym koncie.
Nic nie pobieramy, to tylko link. Stałe kanały (WOC, WOT Cyberkomponent, kwalifikacje ECSC, staże MF), czyli rekrutacje
ciągłe i programy, których nie da się skanować, są w katalogu firm.

Każdy portal działa osobno — jak jeden zmieni stronę, reszta leci dalej, a skan
pokaże `⚠ portal BŁĄD`. Wtedy: zapisz nową odpowiedź jako fixture w
`tests/fixtury/`, popraw `parsuj_<portal>` w `portale.py`, aż przejdą testy:

```bash
py -m unittest -v
```

Wspólny format oferty (poziomy, tryby pracy, umowy, widełki w PLN/mies., stack)
jest opisany na górze `portale.py`.

## Pliki

| Plik | Rola |
|---|---|
| `portale.py` | Portale (JustJoin, NoFluff, Pracuj, theprotocol, Bulldog, SolidJobs, LinkedIn, KPRM, strony firm) → wspólny format. |
| `skan.py` | Skan wszystkich portali równolegle → baza. |
| `baza.py` | SQLite: pamięć, scalanie duplikatów, wygasanie, moje decyzje, dziennik aplikacji. |
| `app.py` | Serwer strony (stdlib `http.server`, tylko 127.0.0.1). |
| `strona.html` | Strona: oferty, szukajka, filtry, dziennik aplikacji, zakładki Firmy i Rekruterzy. |
| `firmy.json` | Katalog pracodawców (cyber, wojsko, zbrojeniówka, państwówka) z linkami. |
| `jobradar.db` | Baza (auto, nie w repo). |
