// Dziennik aplikacji: etapy, termin nastepnego kroku, kontakt, notatki.

import { stan } from "../stan.js";
import * as W from "../wspolne.js";
import { esc } from "../wspolne.js";

export const doZrobienia = a =>
  !W.ZAMKNIETE.has(a.etap) && a.nastepny_krok && a.nastepny_krok <= W.teraz();

export function terminOpis(a) {
  if (W.ZAMKNIETE.has(a.etap)) return W.ETAPY[a.etap];
  if (!a.nastepny_krok) return "bez terminu";
  const z = W.zaIle(a.nastepny_krok);
  if (z < 0) return `follow-up spóźniony ${-z} d`;
  if (z === 0) return "follow-up dziś";
  if (z === 1) return "jutro";
  return `za ${z} d`;
}

// pasek postepu: 4 kroki + wynik. Mini wersja do listy, duza (klikalna) do szczegolow.
function postep(a) {
  const nr = W.KROKI.findIndex(([k]) => k === a.etap);
  // zamknieta sprawa: kroki do najdalszego osiagnietego, potem wynik
  const osiagniety = Math.max(nr, ...a.historia.map(h => W.KROKI.findIndex(([k]) => k === h.etap)));
  return { osiagniety, wynik: W.ZAMKNIETE.has(a.etap) ? a.etap : null };
}

function pasekMini(a) {
  const { osiagniety, wynik } = postep(a);
  const seg = W.KROKI.map((_, i) => `<i class="${i <= osiagniety ? "pelny" : ""}"></i>`).join("");
  return `<span class="postep-mini" aria-label="Etap: ${esc(W.ETAPY[a.etap])}">${seg}<i class="wynik ${wynik || ""}"></i></span>`;
}

function statystyki() {
  const A = stan.aplikacje, n = A.length;
  const byl = (a, zbior) => [a.etap, ...a.historia.map(h => h.etap)].some(e => zbior.includes(e));
  const odp = A.filter(a => byl(a, ["odpowiedz", "rozmowa", "zadanie", "oferta", "odmowa"])).length;
  const rozm = A.filter(a => byl(a, ["rozmowa", "zadanie", "oferta"])).length;
  const ofert = A.filter(a => a.etap === "oferta").length;
  const proc = x => n ? `<small>${Math.round(100 * x / n)}%</small>` : "";
  return `<div class="statystyki">
    <div><b>${n}</b><span>wysłanych</span></div>
    <div><b>${odp}</b>${proc(odp)}<span>odpowiedzi</span></div>
    <div><b>${rozm}</b>${proc(rozm)}<span>rozmów</span></div>
    <div><b>${ofert}</b><span>ofert pracy</span></div>
  </div>`;
}

function pasek() {
  const filtry = [["toku", "W toku"], ["zamkniete", "Zamknięte"], ["wszystkie", "Wszystkie"]];
  return `
    <div class="pasek-wiersz">
      <input type="search" id="szukaj" class="szukaj" value="${esc(stan.szukajAplikacji)}"
             placeholder="Szukaj w stanowiskach, firmach, notatkach" aria-label="Szukaj aplikacji">
      <button class="przycisk glowny" data-akcja="nowa-aplikacja">Dodaj aplikację</button>
    </div>
    <div class="pasek-wiersz">
      <div class="segment" role="group" aria-label="Pokaż">
        ${filtry.map(([k, n]) => `<button data-akcja="filtr-apl" data-filtr="${k}" aria-pressed="${stan.filtrAplikacji === k}">${n}</button>`).join("")}
      </div>
    </div>
    <div class="licznik" id="licznik"></div>`;
}

function grupy() {
  const s = W.slowa(stan.szukajAplikacji);
  const f = stan.filtrAplikacji;
  const lista = stan.aplikacje
    .filter(a => f === "wszystkie" || (f === "zamkniete") === W.ZAMKNIETE.has(a.etap))
    .filter(a => !s.length || s.every(x => W.zwykly([a.tytul, a.firma, a.notatki, a.kontakt].join(" ")).includes(x)));
  const termin = a => a.nastepny_krok || Infinity;
  const pilne = lista.filter(doZrobienia).sort((a, b) => termin(a) - termin(b));
  const wToku = lista.filter(a => !doZrobienia(a) && !W.ZAMKNIETE.has(a.etap)).sort((a, b) => termin(a) - termin(b) || b.kiedy - a.kiedy);
  const zamkniete = lista.filter(a => W.ZAMKNIETE.has(a.etap)).sort((a, b) => b.kiedy - a.kiedy);
  return [
    { naglowek: "Wymaga Twojego ruchu", alarm: true, elementy: pilne },
    { naglowek: "W toku", elementy: wToku },
    { naglowek: "Zamknięte", elementy: zamkniete },
  ].filter(g => g.elementy.length);
}

function wiersz(a, wybrany) {
  const pilny = doZrobienia(a);
  return `
  <button class="wiersz aplikacja${pilny ? " pilny" : ""}${W.ZAMKNIETE.has(a.etap) ? " zamkniety" : ""}${wybrany ? " wybrany" : ""}"
          data-akcja="wybierz" data-id="${a.id}" role="listitem">
    <span class="w-tytul">${esc(a.tytul)}</span>
    <span class="w-prawa"><span class="w-termin${pilny ? " alarm" : ""}">${esc(terminOpis(a))}</span></span>
    <span class="w-firma">${esc(a.firma)}</span>
    <span class="w-opis">${pasekMini(a)}<span>${esc(W.ETAPY[a.etap])}</span></span>
  </button>`;
}

function stanOferty(a) {
  if (a.aktywna === null) return '<p class="znak">Dodana ręcznie</p>';
  if (a.aktywna === false) return '<p class="znak">Oferta zniknęła z portalu, masz jej kopię niżej</p>';
  return '<p class="znak">Oferta wciąż wisi na portalu</p>';
}

function detal(a) {
  const { osiagniety, wynik } = postep(a);
  const z = a.nastepny_krok ? W.zaIle(a.nastepny_krok) : null;
  const kroki = W.KROKI.map(([k, n], i) => `
    <button class="krok${i <= osiagniety ? " pelny" : ""}${a.etap === k ? " biezacy" : ""}"
            data-akcja="etap" data-id="${a.id}" data-etap="${k}" aria-pressed="${a.etap === k}">${n}</button>`).join("");
  const finaly = W.FINALY.map(([k, n]) => `
    <button class="final ${k}${wynik === k ? " biezacy" : ""}" data-akcja="etap" data-id="${a.id}" data-etap="${k}"
            aria-pressed="${wynik === k}">${n}</button>`).join("");
  const szybkie = [[1, "jutro"], [3, "za 3 dni"], [7, "za tydzień"], [14, "za 2 tygodnie"]];
  return `
  <div class="detal-glowa">
    <button class="wstecz" data-akcja="zamknij-detal">Wróć do listy</button>
    <p class="detal-firma">${esc(a.firma)}</p>
    <h2>${a.url ? `<a href="${esc(a.url)}" target="_blank" rel="noopener">${esc(a.tytul)}</a>` : esc(a.tytul)}</h2>
    <p class="detal-meta">Aplikowano ${esc(W.dataPelna(a.kiedy))} (${W.ileTemu(a.kiedy)})</p>
    ${stanOferty(a)}
  </div>

  <section class="sekcja">
    <h3>Etap</h3>
    <div class="kroki" role="group" aria-label="Etap rekrutacji">${kroki}</div>
    <div class="finaly" role="group" aria-label="Wynik">${finaly}</div>
  </section>

  <section class="sekcja${doZrobienia(a) ? " pilna" : ""}">
    <h3>Następny krok</h3>
    ${W.ZAMKNIETE.has(a.etap) ? "<p class=\"cichy\">Sprawa zamknięta, przypomnienie wyłączone.</p>" : `
    <div class="termin">
      <input type="date" data-pole="nastepny_krok" data-id="${a.id}" value="${W.naDate(a.nastepny_krok)}" aria-label="Data następnego kroku">
      <span class="termin-opis${doZrobienia(a) ? " alarm" : ""}">${
        z === null ? "Bez przypomnienia" : z < 0 ? `Spóźnione o ${-z} d. Napisz do rekrutera.` : z === 0 ? "Dziś" : `Za ${z} d`}</span>
    </div>
    <div class="szybkie">
      ${szybkie.map(([d, n]) => `<button class="chip" data-akcja="termin" data-id="${a.id}" data-dni="${d}">${n}</button>`).join("")}
      <button class="chip" data-akcja="termin" data-id="${a.id}" data-dni="">bez przypomnienia</button>
    </div>`}
  </section>

  <section class="sekcja">
    <h3>Kontakt</h3>
    <input type="text" class="pole" data-pole="kontakt" data-id="${a.id}" value="${esc(a.kontakt)}"
           placeholder="Np. Anna Kowalska, HR, anna@firma.pl, link do profilu" aria-label="Kontakt">
    ${W.linkiLudzi(a.firma)}
  </section>

  <section class="sekcja">
    <div class="sekcja-glowa">
      <h3>Notatki</h3>
      <span class="zapisano" id="zapisano"></span>
      <button class="chip" data-akcja="wstaw-date" data-id="${a.id}">Wstaw dzisiejszą datę</button>
    </div>
    <textarea class="pole notatki" id="notatki" data-pole="notatki" data-id="${a.id}"
      placeholder="Pytania z rozmowy, co obiecali, czego się douczyć, widełki z rozmowy, kiedy mają odpisać">${esc(a.notatki)}</textarea>
  </section>

  <section class="sekcja">
    <h3>Oferta z dnia aplikacji</h3>
    <dl class="fakty">
      ${a.wid_od || a.wid_do ? `<div><dt>Widełki</dt><dd>${esc(W.widelki(a))}</dd></div>` : ""}
      ${a.lokacja ? `<div><dt>Gdzie</dt><dd>${esc(a.lokacja)}</dd></div>` : ""}
      ${a.kategoria ? `<div><dt>Dział</dt><dd>${esc(a.kategoria)}</dd></div>` : ""}
    </dl>
    ${a.stack.length ? `<ul class="stack">${a.stack.map(s => `<li>${esc(s)}</li>`).join("")}</ul>` : ""}
    ${!a.wid_od && !a.wid_do && !a.lokacja && !a.stack.length ? '<p class="cichy">Brak szczegółów, wpis dodany ręcznie.</p>' : ""}
  </section>

  <section class="sekcja">
    <h3>Historia</h3>
    <ol class="os-czasu">${a.historia.slice().reverse().map(h =>
      `<li><time>${esc(W.data(h.kiedy))}</time> ${esc(W.ETAPY[h.etap] || h.etap)}</li>`).join("")}</ol>
  </section>

  <div class="strefa-usuwania">
    <button class="przycisk niebezpieczny" data-akcja="usun-aplikacje" data-id="${a.id}">Usuń wpis</button>
  </div>`;
}

function formularz() {
  return `
  <div class="detal-glowa">
    <button class="wstecz" data-akcja="zamknij-detal">Wróć do listy</button>
    <h2>Nowa aplikacja</h2>
    <p class="detal-meta">Dla aplikacji spoza radaru: formularz WOC, nabór KPRM na papierze, polecenie od znajomego.</p>
  </div>
  <form class="formularz" data-akcja="dodaj-aplikacje">
    <label>Stanowisko <input class="pole" name="tytul" required placeholder="Np. Analityk SOC"></label>
    <label>Firma lub urząd <input class="pole" name="firma" required placeholder="Np. Wojska Obrony Cyberprzestrzeni"></label>
    <label>Kiedy aplikowałeś <input class="pole" name="kiedy" type="date" value="${W.naDate(W.teraz())}"></label>
    <label>Link do ogłoszenia <input class="pole" name="url" type="url" placeholder="https://"></label>
    <label>Notatki <textarea class="pole notatki" name="notatki" placeholder="Skąd, przez kogo, co wysłałeś"></textarea></label>
    <div class="akcje-glowne">
      <button class="przycisk glowny" type="submit">Dodaj aplikację</button>
      <button class="przycisk" type="button" data-akcja="zamknij-formularz">Anuluj</button>
    </div>
  </form>`;
}

export const aplikacje = {
  nazwa: "Aplikacje",
  szukaj: { get: () => stan.szukajAplikacji, set: v => { stan.szukajAplikacji = v; } },
  pasek,
  grupy,
  // statystyki tu, nie w pasku: licznik odswieza sie po kazdej zmianie etapu
  licznik: lista => {
    const pilne = lista.filter(doZrobienia).length;
    return statystyki() + `${lista.length} ${W.odmiana(lista.length, "aplikacja", "aplikacje", "aplikacji")}` +
      (pilne ? `, <span class="alarm">${pilne} ${W.odmiana(pilne, "czeka", "czekają", "czeka")} na follow-up</span>` : "");
  },
  id: a => String(a.id),
  znajdz: id => stan.aplikacje.find(a => String(a.id) === String(id)),
  wiersz,
  detal: a => stan.nowaAplikacja ? formularz() : detal(a),
  pusty: () => stan.aplikacje.length
    ? "<p>Nic w tym filtrze.</p>"
    : `<p>Nie masz jeszcze aplikacji.</p>
       <p>Przy ofercie kliknij „Zaaplikowałem” (klawisz <kbd>a</kbd>). Wpis z przypomnieniem o follow-upie pojawi się tutaj.</p>`,
  pustyDetal: () => stan.nowaAplikacja ? formularz() : `<div class="pusty-detal">
      <p>Wybierz aplikację, żeby zmienić etap, termin albo dopisać notatki.</p>
      <button class="przycisk" data-akcja="nowa-aplikacja">Dodaj aplikację spoza radaru</button></div>`,
};
