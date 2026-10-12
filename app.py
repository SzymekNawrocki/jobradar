"""JobRadar — strona w przegladarce (bez zadnych instalacji).

Uruchomienie:
    py app.py
Otwiera sie http://localhost:8010 od razu. Jesli ostatni skan jest starszy
niz pol godziny, w tle skanuje portale (~30 s, strona pokazuje "skanuje"
i sama dociaga wynik), a potem co pol godziny, dopoki okno jest otwarte.

Serwer to wbudowany http.server, slucha tylko na 127.0.0.1 (nikt z sieci
sie nie dobije). Strona (static/: index.html, style.css, moduly js) pobiera
dane z /api/lista i /api/firmy,
a klikniecia wysyla na /api/status, /api/przejrzane i /api/skan.
Dziennik aplikacji: /api/aplikacje (+ /dodaj, /zmien, /usun).
"""

import json
import sys
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import baza
import skan

PORT = 8010
STATIC = (Path(__file__).parent / "static").resolve()  # strona: html, css, moduly js
TYPY = {".html": "text/html", ".css": "text/css", ".js": "text/javascript",
        ".svg": "image/svg+xml", ".json": "application/json"}
FIRMY = Path(__file__).parent / "firmy.json"  # katalog do zakladki "Firmy i panstwowka"
SKAN_STARSZY_NIZ_S = 30 * 60

# jedno polaczenie z baza na caly serwer + zamek, bo zadania ida z roznych watkow
db = baza.polacz(check_same_thread=False)
zamek = threading.Lock()
# osobny zamek na skan: trwa ~30 s (LinkedIn), a lista ma sie w tym czasie
# normalnie wczytywac — baze blokujemy tylko na sam zapis
skanowanie = threading.Lock()


def dane_listy():
    kiedy, bledy = baza.ostatni_skan(db)
    return {
        "oferty": baza.lista(db),
        "skan": {"kiedy": kiedy, "bledy": bledy, "trwa": skanowanie.locked()},
    }


def skanuj():
    """Skanuje portale i zapisuje wynik. Gdy skan juz trwa — czeka na niego."""
    if not skanowanie.acquire(blocking=False):
        with skanowanie:
            return {"nowe": 0, "bledy": []}
    try:
        start = int(time.time())
        wyniki = skan.skanuj()
        with zamek:
            nowe = sum(baza.zapisz_skan(db, wyniki, teraz=start).values())
    finally:
        skanowanie.release()
    print(time.strftime("%H:%M"), f"— skan: {nowe} nowych ofert")
    return {"nowe": nowe, "bledy": [f"{n}: {b}" for n, _, b, _ in wyniki if b]}


def plik_statyczny(sciezka):
    """'/static/js/main.js' -> plik w static/ albo None. Nic spoza static/."""
    if sciezka in ("/", "/index.html"):
        return STATIC / "index.html"
    if not sciezka.startswith("/static/"):
        return None
    plik = (STATIC / sciezka[len("/static/"):].split("?")[0]).resolve()
    if STATIC not in plik.parents or not plik.is_file() or plik.suffix not in TYPY:
        return None
    return plik


def skan_stary():
    with zamek:
        kiedy, _ = baza.ostatni_skan(db)
    return not kiedy or time.time() - kiedy > SKAN_STARSZY_NIZ_S


class Handler(BaseHTTPRequestHandler):
    def _wyslij(self, tresc, kod=200, typ="application/json; charset=utf-8"):
        if not isinstance(tresc, bytes):
            tresc = json.dumps(tresc, ensure_ascii=False).encode("utf-8")
        self.send_response(kod)
        self.send_header("Content-Type", typ)
        self.send_header("Content-Length", str(len(tresc)))
        self.end_headers()
        self.wfile.write(tresc)

    def _cialo(self):
        dlugosc = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(dlugosc) or b"{}")

    def do_GET(self):
        plik = plik_statyczny(self.path)
        if plik:
            self._wyslij(plik.read_bytes(), typ=TYPY[plik.suffix] + "; charset=utf-8")
        elif self.path == "/api/lista":
            with zamek:
                self._wyslij(dane_listy())
        elif self.path == "/api/aplikacje":
            with zamek:
                self._wyslij(baza.aplikacje(db))
        elif self.path == "/api/firmy":
            self._wyslij(FIRMY.read_bytes())
        else:
            self._wyslij({"blad": "nie ma takiej strony"}, 404)

    def do_POST(self):
        try:
            cialo = self._cialo()
            if self.path == "/api/skan":
                self._wyslij(skanuj())
                return
            with zamek:
                if self.path == "/api/status":
                    baza.ustaw_status(db, cialo["id"], cialo.get("status"))
                    self._wyslij({"ok": True})
                elif self.path == "/api/aplikacje/dodaj":
                    id_ = baza.dodaj_aplikacje(db, cialo.get("tytul"), cialo.get("firma"),
                                               cialo.get("url"), cialo.get("notatki"),
                                               cialo.get("kiedy"))
                    self._wyslij({"id": id_})
                elif self.path == "/api/aplikacje/zmien":
                    baza.zmien_aplikacje(db, cialo.pop("id"), **cialo)
                    self._wyslij({"ok": True})
                elif self.path == "/api/aplikacje/usun":
                    baza.usun_aplikacje(db, cialo["id"])
                    self._wyslij({"ok": True})
                elif self.path == "/api/przejrzane":
                    baza.zapisz_ustawienie(db, "przejrzane", int(time.time()))
                    self._wyslij({"ok": True})
                else:
                    self._wyslij({"blad": "nie ma takiej strony"}, 404)
        except (KeyError, ValueError) as e:  # JSONDecodeError to tez ValueError
            self._wyslij({"blad": str(e)}, 400)

    def log_message(self, *a):  # cisza w konsoli
        pass


def skanuj_co_jakis_czas():
    """Watek w tle: dopoki JobRadar dziala, skanuje, gdy ostatni skan sie zestarzeje."""
    while True:
        if skan_stary():
            print(time.strftime("%H:%M"), "— skanuję portale...")
            try:
                skanuj()
            except Exception as e:  # noqa: BLE001 — watek nie moze umrzec
                print("Skan nie wyszedł:", e)
        time.sleep(60)


def main():
    # pierwszy skan (jesli trzeba) robi od razu watek w tle — strona nie czeka
    threading.Thread(target=skanuj_co_jakis_czas, daemon=True).start()
    adres = f"http://localhost:{PORT}"
    print(f"\nJobRadar działa: {adres}   (Ctrl+C, żeby zatrzymać)")
    try:
        webbrowser.open(adres)
    except Exception:
        pass
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
