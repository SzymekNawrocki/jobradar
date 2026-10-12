// Radar: kazda swieza oferta (ostatnie 7 dni, do przejrzenia) to kropka.
// Odleglosc od srodka = wiek (srodek = teraz, brzeg = 7 dni), sektor = portal.
// Magenta = nowa od ostatniego "Przejrzane"; pulsuja tylko nowe z ostatniej
// doby (przy setkach nowych wszystko by migalo). Klikniecie otwiera oferte.

import { PORTALE, esc, hash01, teraz, DZIEN, odmiana } from "./wspolne.js";

const R = 100;
const DNI = 7;
const SEKTORY = Object.keys(PORTALE);

function pozycja(o) {
  const portal = o.portale[0];
  const s = Math.max(0, SEKTORY.indexOf(portal));
  // 0.1..0.9 sektora — kropki nie siadaja na granicy
  const kat = 2 * Math.PI * (s + 0.1 + 0.8 * hash01(o.id)) / SEKTORY.length - Math.PI / 2;
  const wiek = Math.min(DNI, Math.max(0, (teraz() - o.data) / DZIEN));
  const r = 6 + (R - 10) * wiek / DNI;
  return [r * Math.cos(kat), r * Math.sin(kat)];
}

export function rysujRadar(el, oferty, wybranyId) {
  const swieze = oferty.filter(o => !o.status && o.data && teraz() - o.data < DNI * DZIEN);
  const nowych = swieze.filter(o => o.nowe).length;
  const pierscienie = [1, 3, 7].map(d => {
    const r = 6 + (R - 10) * d / DNI;
    return `<circle class="pierscien" r="${r}"/><text class="podpis" x="2" y="${-r - 2}">${d === 1 ? "1 d" : d + " d"}</text>`;
  }).join("");
  const kropki = swieze.map(o => {
    const [x, y] = pozycja(o);
    return `<g class="kropka${o.nowe ? " nowa" : ""}${o.id === wybranyId ? " wybrana" : ""}"
               data-akcja="pokaz-oferte" data-id="${esc(o.id)}" transform="translate(${x.toFixed(1)} ${y.toFixed(1)})">
      <title>${esc(o.tytul)}, ${esc(o.firma)}</title>
      <circle class="trafienie" r="6"/>
      ${o.nowe && teraz() - o.data < DZIEN ? '<circle class="puls" r="3"/>' : ""}
      <circle class="punkt" r="${o.nowe ? 2.6 : 2}"/>
      ${o.id === wybranyId ? '<circle class="obwodka" r="6"/>' : ""}
    </g>`;
  }).join("");
  el.innerHTML = `
    <svg viewBox="-110 -110 220 220" role="img" aria-label="Radar ofert z ostatnich 7 dni">
      <defs>
        <radialGradient id="poswiata"><stop offset="0" stop-color="var(--sygnal)" stop-opacity=".10"/>
          <stop offset="1" stop-color="var(--sygnal)" stop-opacity="0"/></radialGradient>
        <linearGradient id="smuga" x1="0" y1="0" x2="1" y2="0">
          <stop offset="0" stop-color="var(--sygnal)" stop-opacity="0"/>
          <stop offset="1" stop-color="var(--sygnal)" stop-opacity=".35"/></linearGradient>
      </defs>
      <circle r="${R}" fill="url(#poswiata)"/>
      ${pierscienie}
      <line class="os" x1="${-R}" y1="0" x2="${R}" y2="0"/><line class="os" x1="0" y1="${-R}" x2="0" y2="${R}"/>
      <g class="omiatanie"><path d="M0 0 L${R} 0 A${R} ${R} 0 0 0 ${(R * Math.cos(-0.5)).toFixed(1)} ${(R * Math.sin(-0.5)).toFixed(1)} Z" fill="url(#smuga)"/>
        <line x1="0" y1="0" x2="${R}" y2="0"/></g>
      ${kropki}
      <circle class="srodek" r="2.5"/>
    </svg>
    <p class="radar-podpis"><span>${swieze.length} ${odmiana(swieze.length, "oferta", "oferty", "ofert")} z 7 dni</span>
      ${nowych ? `<span class="alarm">${nowych} ${odmiana(nowych, "nowa", "nowe", "nowych")}</span>` : ""}</p>`;
}
