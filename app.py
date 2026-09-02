"""JobRadar — frontend webowy (bez zadnych instalacji).

Uruchomienie:
    py app.py
Potem otworz w przegladarce:  http://localhost:8000

Uzywa wbudowanego serwera Pythona (http.server) — zero zaleznosci.
Oferty pobiera przez radar.zbierz_i_przetworz(), filtrowanie (szukajka,
poziom, kategoria, tylko-nowe) dzieje sie na zywo po stronie przegladarki.
Przycisk "Odswiez" przeskanowuje zrodla na nowo.
"""

import json
import sys
import time
import webbrowser
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from radar import zbierz_i_przetworz, _data

PORT = 8010

# prosty cache w pamieci, zeby nie skanowac przy kazdym odswiezeniu strony
_cache = {"oferty": [], "kiedy": 0}


def dane_do_json(force=False):
    """Zwraca liste ofert jako czysty JSON-owalny format (z cache)."""
    if force or not _cache["oferty"]:
        print("Skanuje zrodla...")
        oferty = zbierz_i_przetworz(zapamietaj=False)
        _cache["oferty"] = [{
            "tytul": o["tytul"], "firma": o["firma"], "lokacja": o["lokacja"],
            "url": o["url"], "kategoria": o["kategoria"], "poziom": o["poziom"],
            "nowa": o["nowa"], "data": _data(o),
        } for o in oferty]
        _cache["kiedy"] = time.time()
        print(f"Gotowe: {len(_cache['oferty'])} ofert.")
    return _cache["oferty"]


def strona():
    oferty = dane_do_json()
    kiedy = datetime.fromtimestamp(_cache["kiedy"]).strftime("%H:%M:%S")
    kategorie = sorted({o["kategoria"] for o in oferty})
    dane_js = json.dumps(oferty, ensure_ascii=False)
    opcje_kat = "".join(f'<option value="{k}">{k}</option>' for k in kategorie)
    return f"""<!doctype html><html lang="pl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>JobRadar</title><style>
 :root{{color-scheme:dark}}
 *{{box-sizing:border-box}}
 body{{background:#0d1117;color:#e6edf3;font:14px/1.5 system-ui,sans-serif;margin:0;padding:24px;max-width:900px;margin:0 auto}}
 header{{display:flex;align-items:center;gap:12px;flex-wrap:wrap;margin-bottom:16px}}
 h1{{font-size:20px;margin:0}}
 .sub{{color:#8b949e;font-size:12px}}
 button,select,input{{background:#161b22;color:#e6edf3;border:1px solid #30363d;
   border-radius:6px;padding:7px 12px;font:inherit}}
 button{{cursor:pointer}} button:hover{{border-color:#58a6ff}}
 .bar{{display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin-bottom:16px}}
 .bar input[type=search]{{flex:1;min-width:180px}}
 .chip{{padding:5px 10px}} .chip.on{{border-color:#58a6ff;background:#1f2b3d}}
 label.check{{display:flex;align-items:center;gap:6px;color:#8b949e;cursor:pointer}}
 a.oferta{{display:grid;grid-template-columns:70px 1fr;gap:2px 12px;padding:12px 14px;
   margin:8px 0;background:#161b22;border:1px solid #30363d;border-radius:8px;
   text-decoration:none;color:inherit;border-left:4px solid #6e7681}}
 a.oferta:hover{{border-color:#58a6ff}}
 a.oferta.junior{{border-left-color:#3fb950}} a.oferta.senior{{border-left-color:#f85149}}
 a.oferta.mid{{border-left-color:#d29922}}
 .lvl{{grid-row:1/3;align-self:center;font-size:11px;text-transform:uppercase;color:#8b949e}}
 .tytul{{font-weight:600}} .badge{{color:#3fb950;font-size:11px}}
 .meta{{color:#8b949e;font-size:12px}}
 #puste{{color:#8b949e;padding:24px 0}}
</style></head><body>
<header>
  <h1>📡 JobRadar</h1>
  <span class="sub">{len(oferty)} ofert · skan {kiedy}</span>
  <span style="flex:1"></span>
  <button onclick="location.href='/refresh'">🔄 Odśwież źródła</button>
</header>
<div class="bar">
  <input type="search" id="szukaj" placeholder="Szukaj (tytuł / firma)..." oninput="rysuj()">
  <select id="kat" onchange="rysuj()"><option value="">— kategoria —</option>{opcje_kat}</select>
  <button class="chip on" data-lvl="entry" onclick="poziom(this)">🎯 entry (bez seniora)</button>
  <button class="chip" data-lvl="junior" onclick="poziom(this)">tylko junior</button>
  <button class="chip" data-lvl="mid" onclick="poziom(this)">mid</button>
  <button class="chip" data-lvl="senior" onclick="poziom(this)">senior</button>
  <button class="chip" data-lvl="" onclick="poziom(this)">wszystkie</button>
  <label class="check"><input type="checkbox" id="nowe" onchange="rysuj()"> tylko 🆕</label>
</div>
<div id="lista"></div>
<div id="puste" hidden>Brak ofert pasujących do filtrów.</div>
<script>
const OFERTY = {dane_js};
let lvl = "entry";  // domyslnie: bez seniora
function poziom(btn){{
  lvl = btn.dataset.lvl;
  document.querySelectorAll('.chip').forEach(c=>c.classList.toggle('on', c===btn));
  rysuj();
}}
function rysuj(){{
  const q = document.getElementById('szukaj').value.toLowerCase();
  const kat = document.getElementById('kat').value;
  const tylkoNowe = document.getElementById('nowe').checked;
  const wynik = OFERTY.filter(o =>
    (!lvl || (lvl==="entry" ? o.poziom!=="senior" : o.poziom===lvl)) &&
    (!kat || o.kategoria===kat) &&
    (!tylkoNowe || o.nowa) &&
    (!q || (o.tytul+' '+o.firma).toLowerCase().includes(q))
  );
  const lista = document.getElementById('lista');
  lista.innerHTML = wynik.map(o => `
    <a class="oferta ${{o.poziom}}" href="${{o.url}}" target="_blank" rel="noopener">
      <span class="lvl">${{o.poziom}}</span>
      <span class="tytul">${{o.nowa?'<span class=badge>🆕</span> ':''}}${{esc(o.tytul)}}</span>
      <span class="meta">${{esc(o.firma)}} · ${{esc(o.lokacja)}} · ${{o.kategoria}} · ${{o.data}}</span>
    </a>`).join('');
  document.getElementById('puste').hidden = wynik.length>0;
}}
function esc(s){{return s.replace(/[&<>]/g,c=>({{'&':'&amp;','<':'&lt;','>':'&gt;'}}[c]));}}
rysuj();
</script>
</body></html>"""


class Handler(BaseHTTPRequestHandler):
    def _wyslij(self, tresc, kod=200, typ="text/html; charset=utf-8"):
        body = tresc.encode("utf-8")
        self.send_response(kod)
        self.send_header("Content-Type", typ)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.startswith("/refresh"):
            dane_do_json(force=True)
            self.send_response(302)
            self.send_header("Location", "/")
            self.end_headers()
        elif self.path == "/" or self.path.startswith("/?"):
            self._wyslij(strona())
        else:
            self._wyslij("Nie ma takiej strony.", 404, "text/plain; charset=utf-8")

    def log_message(self, *a):  # cisza w konsoli
        pass


def main():
    dane_do_json()  # pierwszy skan zanim wystartuje serwer
    adres = f"http://localhost:{PORT}"
    print(f"\nJobRadar działa: {adres}   (Ctrl+C, żeby zatrzymać)")
    try:
        webbrowser.open(adres)
    except Exception:
        pass
    ThreadingHTTPServer(("", PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
