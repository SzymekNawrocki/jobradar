// Formatowanie i slowniki wspolne dla wszystkich widokow. Bez DOM, bez stanu.

export const PORTALE = {
  justjoin: "JustJoin", nofluff: "NoFluff", pracuj: "Pracuj", protocol: "theprotocol",
  bulldog: "Bulldog", solid: "SolidJobs", linkedin: "LinkedIn",
  kprm: "Służba cywilna", kariera: "Strona firmy",
};
// tu tytul bywa ogolny ("specjalista") — o tym, czy to IT, mowi dopiero dzial
export const Z_DZIALEM = new Set(["kprm", "kariera"]);
export const TRYBY = { zdalna: "zdalnie", hybrydowa: "hybrydowo", biuro: "biuro" };
export const POZIOMY = { staz: "staż", junior: "junior", mid: "mid", senior: "senior", lead: "lead" };
export const UMOWY = { b2b: "B2B", uop: "umowa o pracę", zlecenie: "zlecenie", staz: "umowa stażowa", inna: "inna" };

// etapy aplikacji — kolejnosc ma znaczenie (pasek postepu)
export const KROKI = [
  ["wyslane", "Wysłane"], ["odpowiedz", "Odpowiedź"],
  ["rozmowa", "Rozmowa HR"], ["zadanie", "Zadanie lub techniczna"],
];
export const FINALY = [["oferta", "Oferta"], ["odmowa", "Odmowa"], ["cisza", "Brak odpowiedzi"]];
export const ETAPY = Object.fromEntries([...KROKI, ...FINALY]);
export const ZAMKNIETE = new Set(FINALY.map(([k]) => k));

export const DZIEN = 86400;
export const teraz = () => Date.now() / 1000;

export function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g,
    c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

// "Młodszy" -> "mlodszy": szukanie bez polskich znakow i wielkosci liter
export function zwykly(s) {
  return (s || "").normalize("NFD").replace(/[̀-ͯ]/g, "")
    .replace(/ł/g, "l").replace(/Ł/g, "L").toLowerCase();
}
export const slowa = s => zwykly(s).split(/\s+/).filter(Boolean);

// pelne doby od chwili ts: "dzis" = ostatnie 24 h
export const dniTemu = ts => Math.floor((teraz() - ts) / DZIEN);

export function ileTemu(ts) {
  if (!ts) return "";
  const d = dniTemu(ts);
  return d <= 0 ? "dziś" : d === 1 ? "wczoraj" : `${d} ${odmiana(d, "dzień", "dni", "dni")} temu`;
}
// krotko do kolumny listy: "dziś", "1 d", "12 d"
export const wiekKrotko = ts => !ts ? "?" : dniTemu(ts) <= 0 ? "dziś" : `${dniTemu(ts)} d`;

export const data = ts => ts ? new Date(ts * 1000).toLocaleDateString("pl-PL", { day: "numeric", month: "short" }) : "";
export const dataPelna = ts => ts ? new Date(ts * 1000).toLocaleDateString("pl-PL",
  { day: "numeric", month: "long", year: "numeric" }) : "";
export const godzina = ts => new Date(ts * 1000).toLocaleTimeString("pl-PL", { hour: "2-digit", minute: "2-digit" });

// lokalna polnoc <-> "2026-10-12" dla <input type=date>
export function naDate(ts) {
  if (!ts) return "";
  const d = new Date(ts * 1000);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}
export const zDaty = s => s ? Math.floor(new Date(s + "T00:00").getTime() / 1000) : null;
export const dzisPolnoc = () => zDaty(naDate(teraz()));

// za ile dni kalendarzowych termin: <0 = spozniony (godzina nie ma znaczenia)
export const zaIle = ts => Math.round((zDaty(naDate(ts)) - dzisPolnoc()) / DZIEN);

export function odmiana(n, jeden, kilka, wiele) {
  if (n === 1) return jeden;
  const j = n % 10, d = n % 100;
  return j >= 2 && j <= 4 && !(d >= 12 && d <= 14) ? kilka : wiele;
}
export const ileOfert = n => `${n} ${odmiana(n, "oferta", "oferty", "ofert")}`;

export function widelki(o) {
  if (!o.wid_od && !o.wid_do) return "";
  const k = x => x ? `${Math.round(x / 1000)}k` : "?";
  return o.wid_od === o.wid_do || !o.wid_od ? `${k(o.wid_do || o.wid_od)} zł` : `${k(o.wid_od)}–${k(o.wid_do)} zł`;
}

export function miejsce(o) {
  const czesci = [];
  const waw = (o.miasta || []).find(m => /^(warszawa|warsaw)$/i.test(m));
  if (waw) czesci.push("Warszawa");
  else if (o.miasta?.length) czesci.push(o.miasta[0]);
  const t = (o.tryby || []).map(t => TRYBY[t]).filter(Boolean).join(" lub ");
  if (t) czesci.push(t);
  return czesci.join(", ");
}

// Forma prawna ("Sp. z o.o.", "S.A.") psuje wyszukiwanie i grupowanie — ucinamy.
export function nazwaFirmy(firma) {
  return (firma || "")
    .replace(/\b(sp\.?\s*z\s*o\.?\s*o\.?|s\.?\s*a\.?|sp\.?\s*k\.?|sp\.?\s*j\.?|spółka.*)$/gi, "")
    .replace(/[\s,.-]+$/, "").trim();
}
export const kluczFirmy = firma => zwykly(nazwaFirmy(firma));

// Wyszukiwarka osob na LinkedIn. Nic nie pobieramy — to tylko linki,
// otwierasz je zalogowany.
const LI_OSOBY = {
  rekruterzy: '(recruiter OR rekruter OR rekruterka OR "talent acquisition" OR HR)',
  it: '(developer OR programista OR engineer OR inżynier OR security OR cyber OR administrator)',
};
export const linkedinOsoby = (firma, kogo) => "https://www.linkedin.com/search/results/people/?keywords="
  + encodeURIComponent(`"${nazwaFirmy(firma)}" ${LI_OSOBY[kogo]}`);
export const linkedinFirma = firma => "https://www.linkedin.com/search/results/companies/?keywords="
  + encodeURIComponent(nazwaFirmy(firma));

export function linkiLudzi(firma) {
  return `<div class="linki-ludzi">
    <a class="link-zew" href="${esc(linkedinOsoby(firma, "rekruterzy"))}" target="_blank" rel="noopener">Rekruterzy i HR</a>
    <a class="link-zew" href="${esc(linkedinOsoby(firma, "it"))}" target="_blank" rel="noopener">Ludzie z IT (polecenie)</a>
    <a class="link-zew" href="${esc(linkedinFirma(firma))}" target="_blank" rel="noopener">Firma na LinkedIn</a>
  </div>`;
}

// alias "pse" ma pasowac do "PSE S.A.", ale nie do "Pseudo" — cale slowa
export function pasujeAlias(firma, aliasy) {
  const w = s => " " + zwykly(s).replace(/[^a-z0-9]+/g, " ").trim() + " ";
  const f = w(firma);
  return aliasy.some(a => f.includes(w(a)));
}

export function grupujPoFirmie(lista) {
  const grupy = new Map();
  for (const x of lista) {
    const k = nazwaFirmy(x.firma);
    if (!k) continue;
    if (!grupy.has(k)) grupy.set(k, []);
    grupy.get(k).push(x);
  }
  return grupy;
}

// stabilna liczba 0..1 z tekstu — pozycja kropki na radarze
export function hash01(s) {
  let h = 2166136261;
  for (const c of s) h = Math.imul(h ^ c.charCodeAt(0), 16777619);
  return ((h >>> 0) % 10000) / 10000;
}

// Klikalne listy w panelach szczegolow: oferty i aplikacje. Klikniecie
// przenosi do wlasciwego widoku i zaznacza element (main.js).
const STATUS_OFERTY = { aplikowane: "zaaplikowana", ukryte: "ukryta" };

export function pozycjeOfert(lista, ile = 8) {
  const li = lista.slice(0, ile).map(o => `
    <li><button class="pozycja${o.nowe && !o.status ? " nowy" : ""}" data-akcja="pokaz-oferte" data-id="${esc(o.id)}">
      <span class="p-tytul">${esc(o.tytul)}</span>
      <span class="p-opis">${esc([o.firma, widelki(o), ileTemu(o.data), STATUS_OFERTY[o.status]].filter(Boolean).join(", "))}</span>
    </button></li>`).join("");
  const reszta = lista.length > ile ? `<li class="p-wiecej">i ${ileOfert(lista.length - ile)} więcej</li>` : "";
  return `<ul class="pozycje">${li}${reszta}</ul>`;
}

export function pozycjeAplikacji(lista) {
  return `<ul class="pozycje">${lista.map(a => `
    <li><button class="pozycja" data-akcja="pokaz-aplikacje" data-id="${a.id}">
      <span class="p-tytul">${esc(a.tytul)}</span>
      <span class="p-opis">${esc(ETAPY[a.etap])}, aplikowano ${esc(data(a.kiedy))}${a.kontakt ? ", kontakt: " + esc(a.kontakt) : ""}</span>
      ${a.notatki ? `<span class="p-notatka">${esc(a.notatki.length > 140 ? a.notatki.slice(0, 140) + "…" : a.notatki)}</span>` : ""}
    </button></li>`).join("")}</ul>`;
}
