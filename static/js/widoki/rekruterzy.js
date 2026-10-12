// Rekruterzy: kazda firma z Twoich ofert i aplikacji, z linkami do ludzi
// na LinkedIn i kontaktami zapisanymi w aplikacjach.

import { stan } from "../stan.js";
import * as W from "../wspolne.js";
import { esc } from "../wspolne.js";

const POKAZ = 200;  // ~400 firm naraz to za dlugi ekran — reszta po szukajce

function wszystkie() {
  const firmy = new Map();
  const dodaj = (nazwa, pole, x) => {
    const k = W.kluczFirmy(nazwa);
    if (!k) return;
    if (!firmy.has(k)) firmy.set(k, { id: k, nazwa: W.nazwaFirmy(nazwa), oferty: [], aplikacje: [] });
    firmy.get(k)[pole].push(x);
  };
  for (const o of stan.oferty) if (o.status !== "ukryte") dodaj(o.firma, "oferty", o);
  // aplikacje tez wtedy, gdy oferta juz wygasla — tam kontakt jest najcenniejszy
  for (const a of stan.aplikacje) dodaj(a.firma, "aplikacje", a);
  return [...firmy.values()];
}

function elementy() {
  const s = W.slowa(stan.szukajFirm);
  return wszystkie()
    .filter(f => !stan.tylkoAplikowane || f.aplikacje.length)
    .filter(f => s.every(x => W.zwykly(f.nazwa).includes(x)))
    // najpierw tam, gdzie aplikowales (follow-up), potem najwiecej ofert
    .sort((a, b) => b.aplikacje.length - a.aplikacje.length || b.oferty.length - a.oferty.length
      || a.nazwa.localeCompare(b.nazwa, "pl"));
}

function wiersz(f, wybrany) {
  const opis = [f.oferty.length ? W.ileOfert(f.oferty.length) : "",
                f.aplikacje.length ? `aplikowałeś: ${f.aplikacje.length}` : ""].filter(Boolean).join(", ");
  return `
  <button class="wiersz firma${wybrany ? " wybrany" : ""}" data-akcja="wybierz" data-id="${esc(f.id)}" role="listitem">
    <span class="w-tytul">${esc(f.nazwa)}</span>
    <span class="w-prawa">${f.aplikacje.length ? '<span class="licznik-chip">aplikowałeś</span>' : ""}</span>
    <span class="w-opis">${esc(opis)}</span>
  </button>`;
}

function detal(f) {
  const kontakty = f.aplikacje.filter(a => a.kontakt);
  return `
  <div class="detal-glowa">
    <button class="wstecz" data-akcja="zamknij-detal">Wróć do listy</button>
    <h2>${esc(f.nazwa)}</h2>
    <p class="detal-meta">Linki otwierają wyszukiwarkę osób na LinkedIn. Musisz być zalogowany.</p>
  </div>
  <section class="sekcja"><h3>Kogo szukać</h3>${W.linkiLudzi(f.nazwa)}</section>
  ${kontakty.length ? `<section class="sekcja"><h3>Kontakty z Twoich aplikacji</h3>
    <ul class="kontakty">${kontakty.map(a => `<li><strong>${esc(a.kontakt)}</strong>
      <button class="link" data-akcja="pokaz-aplikacje" data-id="${a.id}">${esc(a.tytul)}</button></li>`).join("")}</ul></section>` : ""}
  ${f.aplikacje.length ? `<section class="sekcja"><h3>Twoje aplikacje</h3>${W.pozycjeAplikacji(f.aplikacje)}</section>` : ""}
  ${f.oferty.length ? `<section class="sekcja"><h3>Oferty w radarze</h3>${W.pozycjeOfert(f.oferty, 20)}</section>` : ""}`;
}

export const rekruterzy = {
  nazwa: "Rekruterzy",
  szukaj: { get: () => stan.szukajFirm, set: v => { stan.szukajFirm = v; } },
  pasek: () => `
    <p class="opis-widoku">Firmy z Twoich ofert i aplikacji. Na górze te, do których aplikowałeś: po wysłaniu
      CV warto napisać do rekrutera, a ktoś z zespołu IT może Cię polecić.</p>
    <div class="pasek-wiersz">
      <input type="search" id="szukaj" class="szukaj" value="${esc(stan.szukajFirm)}" placeholder="Szukaj firmy" aria-label="Szukaj firmy">
      <label class="przelacznik"><input type="checkbox" data-akcja="tylko-aplikowane" ${stan.tylkoAplikowane ? "checked" : ""}>
        <span>Tylko gdzie aplikowałem</span></label>
    </div>
    <div class="licznik" id="licznik"></div>`,
  grupy: () => {
    const lista = elementy();
    return [{ elementy: lista.slice(0, POKAZ), ukryto: Math.max(0, lista.length - POKAZ) }];
  },
  licznik: lista => `${lista.length} ${W.odmiana(lista.length, "firma", "firmy", "firm")}`,
  id: f => f.id,
  znajdz: id => wszystkie().find(f => f.id === id),
  wiersz,
  detal,
  pusty: () => stan.tylkoAplikowane ? "<p>Nie aplikowałeś jeszcze nigdzie.</p>" : "<p>Nic nie pasuje.</p>",
  pustyDetal: () => '<div class="pusty-detal"><p>Wybierz firmę, żeby znaleźć rekrutera albo kogoś z zespołu.</p></div>',
};
