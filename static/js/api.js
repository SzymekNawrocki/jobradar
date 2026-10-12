// Jedyne miejsce, ktore rozmawia z serwerem (app.py). Bledy rzucamy z
// komunikatem serwera, zeby toast mogl powiedziec, co poszlo nie tak.

async function odpowiedz(r) {
  const dane = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(dane.blad || `serwer odpowiedział ${r.status}`);
  return dane;
}

const pobierz = sciezka => fetch(sciezka).then(odpowiedz);
const wyslij = (sciezka, cialo) =>
  fetch(sciezka, { method: "POST", body: JSON.stringify(cialo || {}) }).then(odpowiedz);

export const api = {
  lista: () => pobierz("/api/lista"),
  aplikacje: () => pobierz("/api/aplikacje"),
  firmy: () => pobierz("/api/firmy"),
  status: (id, status) => wyslij("/api/status", { id, status }),
  przejrzane: () => wyslij("/api/przejrzane"),
  skan: () => wyslij("/api/skan"),
  dodajAplikacje: pola => wyslij("/api/aplikacje/dodaj", pola),
  zmienAplikacje: (id, pola) => wyslij("/api/aplikacje/zmien", { id, ...pola }),
  usunAplikacje: id => wyslij("/api/aplikacje/usun", { id }),
};
