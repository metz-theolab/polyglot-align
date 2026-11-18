// Appels à l'API REST (app/backend), par chemins relatifs : le serveur qui
// sert le front (Vite en développement, Docker plus tard) les renvoie au backend.

const BASE = "/api/v1";

async function request(path, options = {}) {
  let response;
  try {
    response = await fetch(BASE + path, {
      headers: { "Content-Type": "application/json" },
      ...options,
    });
  } catch {
    throw new Error("API unreachable: is the backend running?");
  }
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail ?? body);
    const error = new Error(detail || `error ${response.status}`);
    error.status = response.status;
    error.body = body;
    throw error;
  }
  return body;
}

/** État des modèles : { status: "loading" | "ready" | "error", detail }. */
export async function health() {
  try {
    return await request("/health");
  } catch (e) {
    if (e.status === 503 && e.body?.status) return e.body;   // loading / error : 503 attendu
    throw e;
  }
}

export const info = () => request("/info");

export const align = (hebrew, greek, algorithm) =>
  request("/align", { method: "POST", body: JSON.stringify({ hebrew, greek, algorithm }) });

// --- lecteur des textes alignés -------------------------------------------------

/** Résultats publiés : [{ id, label, target, language, direction, gold, method }]. */
export const readerCorpora = () => request("/reader/corpora");

/** Livres hébreux alignés : [{ book, chapters, texts: [{ corpus, text }] }]. */
export const readerBooks = () => request("/reader/books");

/** Un chapitre : { book, chapter, verses: [{ ref, words, targets }] }. */
export const readerChapter = (book, chapter) =>
  request(`/reader/${encodeURIComponent(book)}/${encodeURIComponent(chapter)}`);
