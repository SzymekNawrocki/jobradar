// Spina strone: wczytuje dane, rysuje nawigacje / pasek / liste / szczegoly,
// obsluguje klikniecia (jedna delegacja po data-akcja) i skroty klawiszowe.
//
// Kazdy widok (widoki/*.js) ma ten sam ksztalt: pasek(), grupy(), wiersz(),
// detal(), id(), znajdz(), licznik(), pusty(), pustyDetal(). Dzieki temu
// lista, zaznaczanie i klawiatura dzialaja tak samo wszedzie.

import { api } from "./api.js";
import { stan, zapiszUstawienia, wczytajUstawienia } from "./stan.js";
import * as W from "./wspolne.js";
import { oferty, ukryte } from "./widoki/oferty.js";
import { aplikacje, doZrobienia } from "./widoki/aplikacje.js";
import { firmy } from "./widoki/firmy.js";
import { rekruterzy } from "./widoki/rekruterzy.js";
import { rysujRadar } from "./radar.js";
import { toast, blad } from "./toast.js";

const WIDOKI = { oferty, aplikacje, ukryte, firmy, rekruterzy };
const KOLEJNOSC = ["oferty", "aplikacje", "ukryte", "firmy", "rekruterzy"];
const $ = id => document.getElementById(id);
const widok = () => WIDOKI[stan.widok];
const waski = () => matchMedia("(max-width: 1099px)").matches;

// --------------------------------------------------------------------------
// dane
// --------------------------------------------------------------------------

async function odswiez() {
  const [lista, apl] = await Promise.all([api.lista(), api.aplikacje()]);
  stan.oferty = lista.oferty;
  stan.skan = lista.skan;
  stan.aplikacje = apl;
  rysuj({ detal: !pisze() });
  planujOdswiezenie();
}

// serwer skanuje sam co 30 min; strona dociaga wynik co 5 min, a w trakcie
// skanu co 10 s, zeby pokazac wynik od razu
let zegar;
function planujOdswiezenie() {
  clearTimeout(zegar);
  zegar = setTimeout(() => odswiez().catch(console.error), stan.skan.trwa ? 10_000 : 300_000);
}

async function wczytajKatalog() {
  if (stan.katalog) return;
  stan.katalog = await api.firmy();
}

// nie przerysowujemy szczegolow, gdy ktos w nich pisze — zgubilby kursor
const pisze = () => $("detal").contains(document.activeElement)
  && /^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement.tagName);

// --------------------------------------------------------------------------
// rysowanie
// --------------------------------------------------------------------------

function rysuj({ pasek = false, detal = true } = {}) {
  rysujBok();
  if (pasek) $("pasek").innerHTML = widok().pasek();
  rysujListe();
  if (detal) rysujDetal();
  document.body.dataset.widok = stan.widok;
  document.body.classList.toggle("detal-otwarty", stan.detalOtwarty);
}

function rysujBok() {
  rysujRadar($("radar"), stan.oferty, stan.widok === "oferty" ? stan.wybrany.oferty : null);

  const s = stan.skan;
  $("skan").innerHTML = (s.trwa ? '<p class="skanuje">Skanuję portale, to potrwa około minuty</p>' : "")
    + (s.kiedy ? `<p>Ostatni skan ${W.godzina(s.kiedy)}, ${W.dniTemu(s.kiedy) ? W.data(s.kiedy) : "dziś"}</p>`
               : "<p>Jeszcze nie było skanu</p>")
    + (s.bledy || []).map(b => `<p class="alarm">Portal nie odpowiada: ${W.esc(b)}</p>`).join("");
  $("btn-skan").disabled = !!s.trwa;

  const nowe = stan.oferty.filter(o => o.nowe && !o.status).length;
  const pilne = stan.aplikacje.filter(doZrobienia).length;
  const liczniki = {
    oferty: [stan.oferty.filter(o => !o.status).length, nowe ? `${nowe} nowych` : ""],
    aplikacje: [stan.aplikacje.length, pilne ? `${pilne} do follow-upu` : ""],
    ukryte: [stan.oferty.filter(o => o.status === "ukryte").length, ""],
    firmy: ["", ""],
    rekruterzy: ["", ""],
  };
  $("nawigacja").innerHTML = KOLEJNOSC.map((k, i) => {
    const [ile, alarm] = liczniki[k];
    return `<button data-akcja="widok" data-widok="${k}" aria-current="${stan.widok === k ? "page" : "false"}"
              title="Klawisz ${i + 1}">
      <span class="n-nazwa">${WIDOKI[k].nazwa}</span>
      ${ile !== "" ? `<span class="n-ile">${ile}</span>` : ""}
      ${alarm ? `<span class="n-alarm">${alarm}</span>` : ""}
    </button>`;
  }).join("");
  $("btn-przejrzane").classList.toggle("wazny", nowe > 0);
}

// plaska lista elementow w kolejnosci na ekranie — do j/k i zaznaczania
let kolejne = [];

function rysujListe() {
  const w = widok();
  const grupy = w.grupy();
  const wszystkie = grupy.flatMap(g => g.elementy);
  kolejne = wszystkie.map(w.id);

  // zaznaczenie musi byc na liscie; na szerokim ekranie domyslnie pierwszy
  const wyb = stan.wybrany[stan.widok];
  if (!kolejne.includes(wyb) && !(stan.widok === "aplikacje" && stan.nowaAplikacja)) {
    stan.wybrany[stan.widok] = waski() ? null : (kolejne[0] ?? null);
  }

  const html = grupy.map(g => `
    ${g.naglowek ? `<h2 class="grupa${g.alarm ? " alarm" : ""}">${W.esc(g.naglowek)}<span>${g.elementy.length}</span></h2>` : ""}
    ${g.elementy.map(x => w.wiersz(x, w.id(x) === stan.wybrany[stan.widok])).join("")}
    ${g.ukryto ? `<p class="lista-koniec">i ${g.ukryto} więcej, zawęź szukajką</p>` : ""}`).join("");
  $("lista").innerHTML = html || `<div class="pusta-lista">${w.pusty()}</div>`;
  const licznik = $("licznik");
  if (licznik) licznik.innerHTML = w.licznik(wszystkie);
}

function rysujDetal() {
  const w = widok();
  const id = stan.wybrany[stan.widok];
  const x = id != null ? w.znajdz(id) : null;
  const el = $("detal");
  el.innerHTML = x ? w.detal(x) : w.pustyDetal();
  el.scrollTop = 0;
}

function zaznacz(id, { przewin = true, otworz = true } = {}) {
  stan.wybrany[stan.widok] = id;
  stan.nowaAplikacja = false;
  if (otworz) stan.detalOtwarty = true;
  // tylko klasa na wierszach — szybciej niz cala lista i nie skacze
  for (const el of $("lista").querySelectorAll(".wiersz")) {
    const ten = el.dataset.id === String(id);
    el.classList.toggle("wybrany", ten);
    if (ten && przewin) el.scrollIntoView({ block: "nearest" });
  }
  rysujDetal();
  rysujRadar($("radar"), stan.oferty, stan.widok === "oferty" ? id : null);
  document.body.classList.toggle("detal-otwarty", stan.detalOtwarty);
}

async function przelacz(nazwa) {
  if (!WIDOKI[nazwa]) return;
  stan.widok = nazwa;
  stan.detalOtwarty = false;
  stan.nowaAplikacja = false;
  zapiszUstawienia();
  if (nazwa === "firmy") {
    rysuj({ pasek: true });
    try { await wczytajKatalog(); } catch (e) { blad(e); }
  }
  rysuj({ pasek: true });
  $("lista").scrollTop = 0;
}

// --------------------------------------------------------------------------
// przejscia miedzy widokami
// --------------------------------------------------------------------------

function pokazOferte(id) {
  const o = stan.oferty.find(x => x.id === id);
  if (!o) return toast("Tej oferty nie ma już w radarze.");
  if (o.status === "aplikowane") {
    const a = aplikacjaOferty(o);
    if (a) return pokazAplikacje(a.id);
  }
  const cel = o.status === "ukryte" ? "ukryte" : "oferty";
  if (cel === "oferty" && !kolejneDla("oferty").includes(id)) {
    // oferta odfiltrowana — zdejmujemy filtry, zeby bylo ja widac
    Object.assign(stan.filtry, { szukaj: "", dni: 0, tylkoNowe: false, tryby: new Set() });
  }
  stan.widok = cel;
  stan.wybrany[cel] = id;
  stan.detalOtwarty = true;
  rysuj({ pasek: true });
  zaznacz(id);
}

function pokazAplikacje(id) {
  stan.widok = "aplikacje";
  stan.filtrAplikacji = "wszystkie";
  stan.szukajAplikacji = "";
  stan.nowaAplikacja = false;
  stan.wybrany.aplikacje = String(id);
  stan.detalOtwarty = true;
  rysuj({ pasek: true });
  zaznacz(String(id));
}

const kolejneDla = nazwa => WIDOKI[nazwa].grupy().flatMap(g => g.elementy).map(WIDOKI[nazwa].id);

const aplikacjaOferty = o => stan.aplikacje.find(a => a.idy.some(i => o.idy.includes(i)));

// --------------------------------------------------------------------------
// akcje na ofertach
// --------------------------------------------------------------------------

// po decyzji zaznaczenie idzie na nastepna oferte — przegladanie bez myszy
function nastepnyPo(id) {
  const i = kolejne.indexOf(id);
  return kolejne[i + 1] ?? kolejne[i - 1] ?? null;
}

async function ustawStatus(id, status) {
  const o = stan.oferty.find(x => x.id === id);
  const stary = o.status;
  const dalej = nastepnyPo(id);
  await api.status(id, status);
  await odswiez();
  if (stan.widok === "oferty" || stan.widok === "ukryte") {
    stan.wybrany[stan.widok] = dalej;
    rysuj();
    if (dalej) zaznacz(dalej, { otworz: false });
  }
  return { o, stary };
}

async function aplikuj(id) {
  const { o } = await ustawStatus(id, "aplikowane");
  const a = aplikacjaOferty(o);
  toast(`Zapisano w aplikacjach: ${o.tytul}. Przypomnienie o follow-upie za tydzień.`, [
    { etykieta: "Dodaj notatkę", fn: () => { if (a) { pokazAplikacje(a.id); setTimeout(() => $("notatki")?.focus(), 50); } } },
    { etykieta: "Cofnij", fn: () => cofnij(o) },
  ]);
}

async function ukryj(id) {
  const { o } = await ustawStatus(id, "ukryte");
  toast(`Ukryto: ${o.tytul}`, [{ etykieta: "Cofnij", fn: () => cofnij(o) }]);
}

async function przywroc(id) {
  const { o } = await ustawStatus(id, null);
  toast(`Przywrócono do przejrzenia: ${o.tytul}`);
}

async function cofnij(o) {
  try {
    await api.status(o.id, null);
    await odswiez();
    toast("Cofnięte.");
  } catch (e) { blad(e); }
}

// --------------------------------------------------------------------------
// akcje w dzienniku
// --------------------------------------------------------------------------

async function zmienAplikacje(id, pola, { przerysuj = true } = {}) {
  await api.zmienAplikacje(Number(id), pola);
  const a = stan.aplikacje.find(x => String(x.id) === String(id));
  if (przerysuj) {
    stan.aplikacje = await api.aplikacje();
    rysuj();
  } else {
    Object.assign(a, pola);
    rysujBok();
  }
  const z = $("zapisano");
  if (z) z.textContent = `Zapisano ${W.godzina(W.teraz())}`;
}

// notatki i kontakt zapisujemy chwile po ostatnim klawiszu, bez przerysowania
const czekajace = new Map();
function zapiszPozniej(id, pole, wartosc) {
  const k = `${id}/${pole}`;
  clearTimeout(czekajace.get(k));
  const z = $("zapisano");
  if (z) z.textContent = "Zapisuję…";
  czekajace.set(k, setTimeout(() => {
    czekajace.delete(k);
    zmienAplikacje(id, { [pole]: wartosc }, { przerysuj: false }).catch(blad);
  }, 600));
}

function wstawDate(id) {
  const pole = $("notatki");
  const d = new Date();
  const znacznik = `${String(d.getDate()).padStart(2, "0")}.${String(d.getMonth() + 1).padStart(2, "0")}: `;
  const poczatek = pole.selectionStart ?? pole.value.length;
  const przed = pole.value.slice(0, poczatek);
  const wstawka = (przed && !przed.endsWith("\n") ? "\n" : "") + znacznik;
  pole.setRangeText(wstawka, poczatek, pole.selectionEnd ?? poczatek, "end");
  pole.focus();
  zapiszPozniej(id, "notatki", pole.value);
}

// usuwanie na dwa klikniecia — bez okienka confirm()
async function usunAplikacje(id, btn) {
  if (!btn.dataset.pewne) {
    btn.dataset.pewne = "1";
    btn.textContent = "Kliknij jeszcze raz, żeby usunąć";
    setTimeout(() => { delete btn.dataset.pewne; btn.textContent = "Usuń wpis"; }, 3000);
    return;
  }
  const a = stan.aplikacje.find(x => String(x.id) === String(id));
  await api.usunAplikacje(Number(id));
  stan.wybrany.aplikacje = null;
  await odswiez();
  toast(`Usunięto wpis: ${a.tytul}.` + (a.idy.length ? " Oferta wróciła do przejrzenia." : ""));
}

async function dodajAplikacje(form) {
  const f = form.elements;
  const { id } = await api.dodajAplikacje({
    tytul: f.tytul.value, firma: f.firma.value, url: f.url.value,
    notatki: f.notatki.value, kiedy: W.zDaty(f.kiedy.value),
  });
  stan.nowaAplikacja = false;
  stan.aplikacje = await api.aplikacje();
  toast(`Dodano: ${f.tytul.value}. Przypomnienie o follow-upie za tydzień.`);
  pokazAplikacje(id);
}

// --------------------------------------------------------------------------
// klikniecia, pola, klawiatura
// --------------------------------------------------------------------------

const AKCJE = {
  "widok": el => przelacz(el.dataset.widok),
  "wybierz": el => zaznacz(el.dataset.id, { przewin: false }),
  "zamknij-detal": () => { stan.detalOtwarty = false; document.body.classList.remove("detal-otwarty"); },
  "skanuj": async el => {
    el.disabled = true;
    el.textContent = "Skanuję…";
    try {
      const w = await api.skan();
      toast(w.nowe ? `Skan skończony: ${W.ileOfert(w.nowe)} nowych.` : "Skan skończony, nic nowego.");
    } finally {
      el.textContent = "Skanuj teraz";
      await odswiez();
    }
  },
  "przejrzane": async () => {
    await api.przejrzane();
    await odswiez();
    toast("Wszystkie oferty oznaczone jako przejrzane.");
  },
  "aplikuj": el => aplikuj(el.dataset.id),
  "ukryj": el => ukryj(el.dataset.id),
  "przywroc": el => przywroc(el.dataset.id),
  "pokaz-oferte": el => pokazOferte(el.dataset.id),
  "pokaz-aplikacje": el => pokazAplikacje(el.dataset.id),
  "dni": el => { stan.filtry.dni = Number(el.dataset.dni); zapiszUstawienia(); rysuj({ pasek: true }); },
  "tryb": el => {
    const t = el.dataset.tryb, f = stan.filtry.tryby;
    f.has(t) ? f.delete(t) : f.add(t);
    rysuj({ pasek: true });
  },
  "wyczysc-filtry": () => {
    Object.assign(stan.filtry, { szukaj: "", dni: 0, tylkoNowe: false, tryby: new Set() });
    rysuj({ pasek: true });
  },
  "filtr-apl": el => { stan.filtrAplikacji = el.dataset.filtr; rysuj({ pasek: true }); },
  "nowa-aplikacja": () => {
    stan.nowaAplikacja = true;
    stan.detalOtwarty = true;
    rysuj();
    $("detal").querySelector("input[name=tytul]")?.focus();
  },
  "zamknij-formularz": () => { stan.nowaAplikacja = false; stan.detalOtwarty = false; rysuj(); },
  "etap": el => zmienAplikacje(el.dataset.id, { etap: el.dataset.etap }),
  "termin": el => zmienAplikacje(el.dataset.id, {
    nastepny_krok: el.dataset.dni ? W.dzisPolnoc() + Number(el.dataset.dni) * W.DZIEN : null,
  }),
  "wstaw-date": el => wstawDate(el.dataset.id),
  "usun-aplikacje": el => usunAplikacje(el.dataset.id, el),
};

document.addEventListener("click", e => {
  const el = e.target.closest("[data-akcja]");
  if (!el || el.tagName === "FORM" || el.type === "checkbox") return;
  const akcja = AKCJE[el.dataset.akcja];
  if (!akcja) return;
  e.preventDefault();
  Promise.resolve(akcja(el)).catch(blad);
});

document.addEventListener("submit", e => {
  if (e.target.dataset.akcja !== "dodaj-aplikacje") return;
  e.preventDefault();
  dodajAplikacje(e.target).catch(blad);
});

document.addEventListener("input", e => {
  const el = e.target;
  if (el.id === "szukaj") {
    widok().szukaj.set(el.value);
    rysujListe();
    rysujDetal();
  } else if (el.dataset.pole && el.dataset.pole !== "nastepny_krok") {
    zapiszPozniej(el.dataset.id, el.dataset.pole, el.value);
  }
});

document.addEventListener("change", e => {
  const el = e.target;
  if (el.dataset.pole === "nastepny_krok") {
    zmienAplikacje(el.dataset.id, { nastepny_krok: W.zDaty(el.value) }).catch(blad);
  } else if (el.dataset.akcja === "tylko-nowe") {
    stan.filtry.tylkoNowe = el.checked;
    rysuj();
  } else if (el.dataset.akcja === "tylko-aplikowane") {
    stan.tylkoAplikowane = el.checked;
    rysuj();
  }
});

function przesun(o) {
  if (!kolejne.length) return;
  const i = kolejne.indexOf(stan.wybrany[stan.widok]);
  const nowy = kolejne[Math.min(kolejne.length - 1, Math.max(0, i === -1 ? 0 : i + o))];
  zaznacz(nowy, { otworz: !waski() || stan.detalOtwarty });
}

document.addEventListener("keydown", e => {
  if (e.ctrlKey || e.metaKey || e.altKey) return;
  const pole = /^(INPUT|TEXTAREA|SELECT)$/.test(e.target.tagName);
  if (e.key === "Escape") {
    if (pole) e.target.blur();
    else if (stan.detalOtwarty) AKCJE["zamknij-detal"]();
    return;
  }
  if (pole) return;
  const id = stan.wybrany[stan.widok];
  const naOfertach = stan.widok === "oferty" || stan.widok === "ukryte";
  const akcje = {
    j: () => przesun(1), ArrowDown: () => przesun(1),
    k: () => przesun(-1), ArrowUp: () => przesun(-1),
    "/": () => $("szukaj")?.focus(),
    a: () => stan.widok === "oferty" && id && aplikuj(id),
    h: () => naOfertach && id && (stan.widok === "oferty" ? ukryj(id) : przywroc(id)),
    o: () => {
      const x = id && widok().znajdz(id);
      if (x?.url) window.open(x.url, "_blank", "noopener");
    },
    ...Object.fromEntries(KOLEJNOSC.map((k, i) => [String(i + 1), () => przelacz(k)])),
  };
  const fn = akcje[e.key];
  if (!fn) return;
  e.preventDefault();
  Promise.resolve(fn()).catch(blad);
});

// --------------------------------------------------------------------------
// start
// --------------------------------------------------------------------------

wczytajUstawienia();
if (!WIDOKI[stan.widok]) stan.widok = "oferty";
rysuj({ pasek: true });
(stan.widok === "firmy" ? wczytajKatalog() : Promise.resolve())
  .then(odswiez)
  .then(() => rysuj({ pasek: true }))
  .catch(e => {
    $("lista").innerHTML = `<div class="pusta-lista"><p>Nie mogę połączyć się z radarem: ${W.esc(e.message)}</p>
      <p>Sprawdź, czy działa <code>py app.py</code>, i odśwież stronę.</p></div>`;
  });
