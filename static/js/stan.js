// Caly stan strony w jednym obiekcie. Widoki tylko z niego czytaja;
// zmieniaja go akcje w main.js (po odpowiedzi serwera).

export const stan = {
  oferty: [],       // /api/lista — aktywne ogloszenia z moim statusem
  aplikacje: [],    // /api/aplikacje — dziennik
  katalog: null,    // /api/firmy — firmy.json, wczytywany przy pierwszym wejsciu
  skan: {},         // { kiedy, bledy, trwa }

  widok: "oferty",  // oferty | aplikacje | ukryte | firmy | rekruterzy
  // zaznaczony element osobno w kazdym widoku — powrot do widoku go pamieta
  wybrany: { oferty: null, aplikacje: null, ukryte: null, firmy: null, rekruterzy: null },
  // na waskim ekranie szczegoly zaslaniaja liste — otwarte tylko po wyborze
  detalOtwarty: false,

  filtry: { szukaj: "", dni: 7, tryby: new Set(), tylkoNowe: false },
  filtrAplikacji: "toku",  // toku | zamkniete | wszystkie
  szukajAplikacji: "",
  szukajFirm: "",
  tylkoAplikowane: false,
  nowaAplikacja: false,    // formularz recznego dodawania w panelu szczegolow
};

// ulubiony widok i swiezosc pamietamy miedzy wizytami (tylko wygoda)
const KLUCZ = "jobradar.ui";
export function zapiszUstawienia() {
  try {
    localStorage.setItem(KLUCZ, JSON.stringify({ widok: stan.widok, dni: stan.filtry.dni }));
  } catch { /* prywatne okno — trudno */ }
}
export function wczytajUstawienia() {
  try {
    const u = JSON.parse(localStorage.getItem(KLUCZ) || "{}");
    if (u.widok) stan.widok = u.widok;
    if (typeof u.dni === "number") stan.filtry.dni = u.dni;
  } catch { /* brak lub uszkodzone — zostaja domyslne */ }
}
