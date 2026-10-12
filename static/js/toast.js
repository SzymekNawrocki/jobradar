// Powiadomienia na dole ekranu, z opcjonalnymi akcjami (np. "Cofnij").

const CZAS_MS = 12000;  // dosc, zeby przeczytac i kliknac "Cofnij"

export function toast(tekst, akcje = [], { blad = false } = {}) {
  const el = document.createElement("div");
  el.className = "toast" + (blad ? " blad" : "");
  el.innerHTML = `<span></span>`;
  el.firstChild.textContent = tekst;
  for (const { etykieta, fn } of akcje) {
    const b = document.createElement("button");
    b.textContent = etykieta;
    b.addEventListener("click", () => { zamknij(); fn(); });
    el.append(b);
  }
  const kontener = document.getElementById("toasty");
  // jeden naraz — kolejny zastepuje poprzedni (szybkie "a a a" w liscie)
  kontener.replaceChildren(el);
  // pod kursorem nie znika — ktos wlasnie celuje w "Cofnij"
  let zegar = setTimeout(zamknij, CZAS_MS);
  el.addEventListener("mouseenter", () => clearTimeout(zegar));
  el.addEventListener("mouseleave", () => { zegar = setTimeout(zamknij, CZAS_MS / 2); });
  function zamknij() { clearTimeout(zegar); el.remove(); }
}

export const blad = e => toast(`Nie udało się: ${e.message}`, [], { blad: true });
