// Firmy i panstwowka: to, co radar ma teraz z urzedow i stron firm, plus
// katalog pracodawcow z firmy.json (cyber, wojsko, zbrojeniowka, panstwowe).

import { stan } from "../stan.js";
import * as W from "../wspolne.js";
import { esc } from "../wspolne.js";

const widoczne = () => stan.oferty.filter(o => o.status !== "ukryte");

function elementy() {
  const s = W.slowa(stan.szukajFirm);
  const pasuje = nazwa => s.every(x => W.zwykly(nazwa).includes(x));
  const grupy = [];

  // 1. urzedy i strony firm — co jest w radarze w tej chwili
  const zrodla = widoczne().filter(o => o.portale.some(p => W.Z_DZIALEM.has(p)));
  const teraz = [...W.grupujPoFirmie(zrodla)]
    .sort((a, b) => b[1].length - a[1].length)
    .map(([nazwa, oferty]) => ({ id: "teraz:" + nazwa, nazwa, oferty, aliasy: null }))
    .filter(f => pasuje(f.nazwa));
  if (teraz.length) grupy.push({ naglowek: "Teraz w radarze: urzędy i strony firm", elementy: teraz });

  // 2. katalog
  for (const k of stan.katalog?.kategorie || []) {
    const firmy = k.firmy
      .map(f => ({ ...f, id: "kat:" + f.nazwa,
                   oferty: f.aliasy.length ? widoczne().filter(o => W.pasujeAlias(o.firma, f.aliasy)) : [] }))
      .filter(f => pasuje(f.nazwa + " " + f.opis));
    if (firmy.length) grupy.push({ naglowek: k.nazwa, elementy: firmy });
  }
  return grupy;
}

const aplikacjeFirmy = f => stan.aplikacje.filter(a => f.aliasy
  ? W.pasujeAlias(a.firma, f.aliasy) || W.kluczFirmy(a.firma) === W.kluczFirmy(f.nazwa)
  : W.kluczFirmy(a.firma) === W.kluczFirmy(f.nazwa));

function wiersz(f, wybrany) {
  const n = f.oferty.length;
  const apl = aplikacjeFirmy(f).length;
  return `
  <button class="wiersz firma${wybrany ? " wybrany" : ""}" data-akcja="wybierz" data-id="${esc(f.id)}" role="listitem">
    <span class="w-tytul">${esc(f.nazwa)}</span>
    <span class="w-prawa">${n ? `<span class="licznik-chip">${n}</span>` : ""}</span>
    <span class="w-opis">${esc([f.opis ? f.opis.split(". ")[0] : "", apl ? `aplikowałeś: ${apl}` : ""].filter(Boolean).join(". "))}</span>
  </button>`;
}

function detal(f) {
  const apl = aplikacjeFirmy(f);
  return `
  <div class="detal-glowa">
    <button class="wstecz" data-akcja="zamknij-detal">Wróć do listy</button>
    <h2>${esc(f.nazwa)}</h2>
    ${f.opis ? `<p class="detal-meta">${esc(f.opis)}</p>` : ""}
  </div>
  ${f.linki?.length ? `<div class="akcje-glowne">${f.linki.map(([n, url], i) =>
    `<a class="przycisk${i === 0 ? " glowny" : ""}" href="${esc(url)}" target="_blank" rel="noopener">${esc(n)}</a>`).join("")}</div>` : ""}
  ${f.aliasy === null || f.linkedin ? `
  <section class="sekcja"><h3>Ludzie w firmie</h3>${W.linkiLudzi(f.linkedin || f.nazwa)}</section>` : ""}
  ${apl.length ? `<section class="sekcja"><h3>Twoje aplikacje</h3>${W.pozycjeAplikacji(apl)}</section>` : ""}
  <section class="sekcja">
    <h3>${f.oferty.length ? `${W.ileOfert(f.oferty.length)} w radarze` : "Oferty w radarze"}</h3>
    ${f.oferty.length ? W.pozycjeOfert(f.oferty, 20)
      : `<p class="cichy">${f.aliasy?.length ? "Teraz nic. Radar sprawdza co 30 minut." : "To program albo kanał rekrutacji, nie pojedyncze oferty. Sprawdzaj go ręcznie."}</p>`}
  </section>`;
}

export const firmy = {
  nazwa: "Firmy i państwówka",
  szukaj: { get: () => stan.szukajFirm, set: v => { stan.szukajFirm = v; } },
  pasek: () => `
    <p class="opis-widoku">Pracodawcy z cyber, wojska, zbrojeniówki i administracji: strony kariery, ludzie
      i ich oferty w radarze. Katalog edytujesz w pliku <code>firmy.json</code>.</p>
    <div class="pasek-wiersz"><input type="search" id="szukaj" class="szukaj" value="${esc(stan.szukajFirm)}"
      placeholder="Szukaj firmy lub urzędu" aria-label="Szukaj firmy"></div>
    <div class="licznik" id="licznik"></div>`,
  grupy: elementy,
  licznik: lista => `${lista.length} ${W.odmiana(lista.length, "pozycja", "pozycje", "pozycji")}`,
  id: f => f.id,
  znajdz: id => elementy().flatMap(g => g.elementy).find(f => f.id === id),
  wiersz,
  detal,
  pusty: () => stan.katalog ? "<p>Nic nie pasuje.</p>" : "<p>Wczytuję katalog…</p>",
  pustyDetal: () => '<div class="pusty-detal"><p>Wybierz firmę, żeby zobaczyć linki, ludzi i oferty.</p></div>',
};
