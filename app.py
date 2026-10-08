"""JobRadar — strona w przegladarce (bez zadnych instalacji).

Uruchomienie:
    py app.py
Otwiera sie http://localhost:8010 . Jesli ostatni skan jest starszy niz
pol godziny, najpierw skanuje portale (~10 s), a potem co pol godziny
w tle, dopoki okno jest otwarte.

Serwer to wbudowany http.server, slucha tylko na 127.0.0.1 (nikt z sieci
sie nie dobije). Strona (strona.html) pobiera dane z /api/lista,
a klikniecia wysyla na /api/status, /api/przejrzane i /api/skan.
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
from skan import skanuj_i_zapisz

PORT = 8010
STRONA = Path(__file__).parent / "strona.html"
SKAN_STARSZY_NIZ_S = 30 * 60

# jedno polaczenie z baza na caly serwer + zamek, bo zadania ida z roznych watkow
db = baza.polacz(check_same_thread=False)
zamek = threading.Lock()


def dane_listy():
    kiedy, bledy = baza.ostatni_skan(db)
    return {
        "oferty": baza.lista(db),
        "skan": {"kiedy": kiedy, "bledy": bledy},
    }


def skanuj():
    start, wyniki, nowe = skanuj_i_zapisz(db)
    print(f"Skan: {sum(nowe.values())} nowych ofert")
    return {"nowe": sum(nowe.values()),
            "bledy": [f"{n}: {b}" for n, _, b, _ in wyniki if b]}


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
        if self.path in ("/", "/index.html"):
            self._wyslij(STRONA.read_bytes(), typ="text/html; charset=utf-8")
        elif self.path == "/api/lista":
            with zamek:
                self._wyslij(dane_listy())
        else:
            self._wyslij({"blad": "nie ma takiej strony"}, 404)

    def do_POST(self):
        try:
            cialo = self._cialo()
            with zamek:
                if self.path == "/api/status":
                    baza.ustaw_status(db, cialo["id"], cialo.get("status"))
                    self._wyslij({"ok": True})
                elif self.path == "/api/przejrzane":
                    baza.zapisz_ustawienie(db, "przejrzane", int(time.time()))
                    self._wyslij({"ok": True})
                elif self.path == "/api/skan":
                    self._wyslij(skanuj())
                else:
                    self._wyslij({"blad": "nie ma takiej strony"}, 404)
        except (KeyError, ValueError) as e:  # JSONDecodeError to tez ValueError
            self._wyslij({"blad": str(e)}, 400)

    def log_message(self, *a):  # cisza w konsoli
        pass


def skanuj_co_jakis_czas():
    """Watek w tle: dopoki JobRadar dziala, skanuje, gdy ostatni skan sie zestarzeje."""
    while True:
        with zamek:
            kiedy, _ = baza.ostatni_skan(db)
            if not kiedy or time.time() - kiedy > SKAN_STARSZY_NIZ_S:
                print(time.strftime("%H:%M"), "— skanuję portale...")
                try:
                    skanuj()
                except Exception as e:  # noqa: BLE001 — watek nie moze umrzec
                    print("Skan nie wyszedł:", e)
        time.sleep(60)


def main():
    kiedy, _ = baza.ostatni_skan(db)
    if not kiedy or time.time() - kiedy > SKAN_STARSZY_NIZ_S:
        print("Ostatni skan jest stary — skanuję portale...")
        skanuj()
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
