// Widoki "Oferty" (do przejrzenia) i "Ukryte" — ta sama lista, inny status.

import { stan } from "../stan.js";
import * as W from "../wspolne.js";
import { esc } from "../wspolne.js";

function pasuje(o, status) {
  if ((o.status || "") !== status) return false;
  const f = stan.filtry;
  if (!status) {
    // swiezosc od PIERWSZEJ publikacji; oferty bez daty tylko w "wszystkie"
    if (f.dni && (!o.data || W.dniTemu(o.data) >= f.dni)) return false;
    if (f.tylkoNowe && !o.nowe) return false;
    // oferty bez podanego trybu zostawiamy — nie wiadomo, czy nie pasuja
    if (f.tryby.size && o.tryby.length && !o.tryby.some(t => f.tryby.has(t))) return false;
  }
  const s = W.slowa(f.szukaj);
  if (s.length) {
    const tekst = W.zwykly([o.tytul, o.firma, o.kategoria, ...o.stack, ...o.miasta].join(" "));
    if (!s.every(x => tekst.includes(x))) return false;
  }
  return true;
}

// aplikacje do tej samej firmy — zeby nie aplikowac dwa razy w ciemno
export const aplikacjeDoFirmy = firma =>
  stan.aplikacje.filter(a => W.kluczFirmy(a.firma) === W.kluczFirmy(firma));

function pasekOfert() {
  const f = stan.filtry;
  const dni = [[1, "dziś"], [3, "3 dni"], [7, "tydzień"], [0, "wszystkie"]];
  return `
    <div class="pasek-wiersz">
      <input type="search" id="szukaj" class="szukaj" value="${esc(f.szukaj)}"
             placeholder="Szukaj w tytule, firmie, technologii, np. „python junior”" aria-label="Szukaj ofert">
    </div>
    <div class="pasek-wiersz">
      <div class="segment" role="group" aria-label="Opublikowane w ciągu">
        ${dni.map(([d, n]) => `<button data-akcja="dni" data-dni="${d}" aria-pressed="${f.dni === d}">${n}</button>`).join("")}
      </div>
      <div class="segment" role="group" aria-label="Tryb pracy">
        ${Object.entries(W.TRYBY).map(([t, n]) =>
          `<button data-akcja="tryb" data-tryb="${t}" aria-pressed="${f.tryby.has(t)}">${n}</button>`).join("")}
      </div>
      <label class="przelacznik"><input type="checkbox" data-akcja="tylko-nowe" ${f.tylkoNowe ? "checked" : ""}>
        <span>Tylko nowe</span></label>
    </div>
    <div class="licznik" id="licznik"></div>`;
}

function wiersz(o, wybrany) {
  const dzial = o.portale.some(p => W.Z_DZIALEM.has(p)) && o.kategoria ? o.kategoria : "";
  return `
  <button class="wiersz${o.nowe && !o.status ? " nowy" : ""}${wybrany ? " wybrany" : ""}"
          data-akcja="wybierz" data-id="${esc(o.id)}" role="listitem">
    <span class="w-tytul">${esc(o.tytul)}</span>
    <span class="w-prawa">${W.widelki(o) ? `<span class="w-kasa">${esc(W.widelki(o))}</span>` : ""}
      <span class="w-wiek" title="${o.data ? "Opublikowana " + esc(W.dataPelna(o.data)) : "Data publikacji nieznana"}">${W.wiekKrotko(o.data)}</span></span>
    <span class="w-firma">${esc(o.firma)}</span>
    <span class="w-opis">${esc([W.miejsce(o), dzial].filter(Boolean).join(", "))}</span>
  </button>`;
}

const fakt = (nazwa, wartosc) => wartosc ? `<div><dt>${nazwa}</dt><dd>${wartosc}</dd></div>` : "";

function detal(o) {
  const ukryta = o.status === "ukryte";
  const wczesniej = aplikacjeDoFirmy(o.firma);
  const inne = stan.oferty.filter(x => x.id !== o.id && !x.status && W.kluczFirmy(x.firma) === W.kluczFirmy(o.firma));
  const dzial = o.portale.some(p => W.Z_DZIALEM.has(p)) ? o.kategoria : "";
  return `
  <div class="detal-glowa">
    <button class="wstecz" data-akcja="zamknij-detal">Wróć do listy</button>
    <p class="detal-firma">${esc(o.firma)}</p>
    <h2>${esc(o.tytul)}</h2>
    ${o.nowe && !o.status ? '<p class="znak alarm">Nowa od ostatniego przeglądania</p>' : ""}
  </div>

  <div class="akcje-glowne">
    ${ukryta
      ? `<button class="przycisk glowny" data-akcja="przywroc" data-id="${esc(o.id)}">Przywróć do przejrzenia <kbd>h</kbd></button>`
      : `<button class="przycisk glowny" data-akcja="aplikuj" data-id="${esc(o.id)}">Zaaplikowałem <kbd>a</kbd></button>
         <button class="przycisk" data-akcja="ukryj" data-id="${esc(o.id)}">Ukryj <kbd>h</kbd></button>`}
    <a class="przycisk" href="${esc(o.url)}" target="_blank" rel="noopener">Otwórz ogłoszenie <kbd>o</kbd></a>
  </div>

  ${wczesniej.length ? `
  <div class="uwaga">
    <p><strong>Już aplikowałeś do tej firmy.</strong> Sprawdź notatki, zanim wyślesz kolejne CV.</p>
    ${W.pozycjeAplikacji(wczesniej)}
  </div>` : ""}

  <dl class="fakty">
    ${fakt("Widełki", esc(W.widelki(o)) || "nie podano")}
    ${fakt("Gdzie", esc(W.miejsce(o)) || "nie podano")}
    ${fakt("Poziom", esc(o.poziomy.map(p => W.POZIOMY[p]).join(", ")))}
    ${fakt("Umowa", esc(o.umowy.map(u => W.UMOWY[u] || u).join(", ")))}
    ${fakt("Opublikowana", o.data ? `${esc(W.dataPelna(o.data))} (${W.ileTemu(o.data)})` : "nie wiadomo")}
    ${fakt("Wygasa", o.wygasa ? esc(W.dataPelna(o.wygasa)) : "")}
    ${fakt("Dział", esc(dzial))}
    ${fakt("W radarze od", esc(W.dataPelna(o.pierwszy_raz)))}
  </dl>

  ${o.stack.length ? `<ul class="stack">${o.stack.map(s => `<li>${esc(s)}</li>`).join("")}</ul>` : ""}

  <section class="sekcja">
    <h3>Ogłoszenie na ${o.linki.length > 1 ? `${o.linki.length} portalach` : "portalu"}</h3>
    <div class="linki-ludzi">${o.linki.map(l =>
      `<a class="link-zew" href="${esc(l.url)}" target="_blank" rel="noopener">${esc(W.PORTALE[l.portal] || l.portal)}</a>`).join("")}</div>
  </section>

  <section class="sekcja">
    <h3>Ludzie w firmie</h3>
    ${W.linkiLudzi(o.firma)}
  </section>

  ${inne.length ? `
  <section class="sekcja">
    <h3>Inne oferty tej firmy</h3>
    ${W.pozycjeOfert(inne)}
  </section>` : ""}`;
}

function stworz(status) {
  return {
    nazwa: status ? "Ukryte" : "Oferty",
    szukaj: { get: () => stan.filtry.szukaj, set: v => { stan.filtry.szukaj = v; } },
    pasek: () => status
      ? `<div class="pasek-wiersz"><input type="search" id="szukaj" class="szukaj" value="${esc(stan.filtry.szukaj)}"
           placeholder="Szukaj w ukrytych" aria-label="Szukaj w ukrytych"></div><div class="licznik" id="licznik"></div>`
      : pasekOfert(),
    grupy: () => [{ elementy: stan.oferty.filter(o => pasuje(o, status)) }],
    licznik: lista => {
      const n = lista.length;
      const nowych = status ? 0 : lista.filter(o => o.nowe).length;
      return `${W.ileOfert(n)}` + (nowych ? `, w tym <span class="alarm">${nowych} ${W.odmiana(nowych, "nowa", "nowe", "nowych")}</span>` : "");
    },
    id: o => o.id,
    znajdz: id => stan.oferty.find(o => o.id === id && (o.status || "") === status),
    wiersz,
    detal,
    pusty: () => status
      ? "<p>Nic nie ukryłeś. Klawisz <kbd>h</kbd> ukrywa zaznaczoną ofertę.</p>"
      : stan.oferty.length
        ? `<p>Żadna oferta nie pasuje do filtrów.</p>
           <button class="przycisk" data-akcja="wyczysc-filtry">Pokaż wszystkie oferty</button>`
        : "<p>Radar jeszcze nic nie znalazł. Kliknij „Skanuj teraz”.</p>",
    pustyDetal: () => `<div class="pusty-detal"><p>Wybierz ofertę z listy.</p>
      <p>Klawisze <kbd>j</kbd> i <kbd>k</kbd> przechodzą między ofertami.</p></div>`,
  };
}

export const oferty = stworz("");
export const ukryte = stworz("ukryte");
