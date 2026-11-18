// Calculs du lecteur des textes alignés, sans React (testés par reader.test.js).
//
// Réponse de l'API (GET /api/v1/reader/{livre}/{chapitre}), par verset :
//   words   : mots hébreux pivots [{ text, graphic }] (graphic false : ס, פ, ׀)
//   targets : un par texte cible [{ corpus, text, ref, tokens, links: [[w, j]], verdicts }]
//             w : mot pivot, j : token cible ; verdicts : par mot pivot (LXX) ou null
import { tone } from "./alignment.js";

export { tone };

/** Clé d'un texte cible : "eflomal_unvocalized/JudgA". */
export const targetKey = (t) => `${t.corpus}/${t.text}`;

/**
 * Modèle d'affichage d'un verset, pour les textes cibles `shown` (clés).
 * - words   : [{ w, text, graphic, tone, cells: { clé: [{ j, text }] }, verdicts: { clé: verdict } }]
 * - targets : [{ key, corpus, text, ref, tokens: [{ j, text, tone }] }], dans l'ordre de l'API
 * - wToJ, jToW : { clé: Map(w -> [j]) }, { clé: Map(j -> [w]) }
 */
export function buildVerse(verse, shown) {
  const targets = verse.targets.filter((t) => shown.includes(targetKey(t)));
  const words = verse.words.map((word, w) => ({
    w, text: word.text, graphic: word.graphic, tone: tone(w), cells: {}, verdicts: {},
  }));
  const wToJ = {};
  const jToW = {};
  const out = targets.map((t) => {
    const key = targetKey(t);
    const a = new Map();
    const b = new Map();
    for (const [w, j] of t.links) {
      if (!a.has(w)) a.set(w, []);
      if (!b.has(j)) b.set(j, []);
      a.get(w).push(j);
      b.get(j).push(w);
    }
    wToJ[key] = a;
    jToW[key] = b;
    for (const word of words) {
      word.cells[key] = (a.get(word.w) || []).map((j) => ({ j, text: t.tokens[j] }));
      if (t.verdicts) word.verdicts[key] = t.verdicts[word.w];
    }
    // couleur d'un token cible : celle du premier mot hébreu qui lui est relié
    const tokens = t.tokens.map((text, j) => {
      const ws = b.get(j);
      return { j, text, tone: ws ? tone(Math.min(...ws)) : null };
    });
    return { key, corpus: t.corpus, text: t.text, ref: t.ref, tokens };
  });
  return { ref: verse.ref, words, targets: out, wToJ, jToW };
}

/**
 * Ce qu'il faut surligner au survol, l'hébreu servant de pivot :
 * - un mot hébreu (hover = { w }) : lui et ses correspondants dans chaque cible ;
 * - un token cible (hover = { key, j }) : lui, les mots hébreux reliés, et
 *   leurs correspondants dans les autres cibles (grec -> hébreu -> syriaque).
 * Renvoie { words: Set(w), tokens: { clé: Set(j) } }, ou null.
 */
export function related(model, hover) {
  if (!hover) return null;
  const words = new Set();
  if (hover.key === undefined) words.add(hover.w);
  else (model.jToW[hover.key]?.get(hover.j) || []).forEach((w) => words.add(w));
  const tokens = {};
  for (const t of model.targets) {
    tokens[t.key] = new Set();
    for (const w of words) (model.wToJ[t.key].get(w) || []).forEach((j) => tokens[t.key].add(j));
  }
  if (hover.key !== undefined) tokens[hover.key]?.add(hover.j);
  return { words, tokens };
}

/** "Gen.1.3", "Gen 1:3", "gen 1", "1Sam 3,4" -> { book, chapter, verse } (livre
 *  retrouvé dans `books`, sans tenir compte de la casse), ou null. */
export function parseRef(text, books) {
  const m = text.trim().match(/^(\d?\s*[A-Za-z]+)[\s.]*(\d+)(?:[.:,\s]+(\d+))?$/);
  if (!m) return null;
  const name = m[1].replace(/\s+/g, "").toLowerCase();
  const book = books.find((b) => b.toLowerCase() === name);
  if (!book) return null;
  return { book, chapter: m[2], verse: m[3] || null };
}

/** Chapitre voisin (delta = -1 ou +1), en passant au livre précédent ou
 *  suivant ; null au bout. books : [{ book, chapters }]. */
export function neighbour(books, book, chapter, delta) {
  const b = books.findIndex((x) => x.book === book);
  if (b < 0) return null;
  const c = books[b].chapters.indexOf(chapter) + delta;
  if (c >= 0 && c < books[b].chapters.length) return { book, chapter: books[b].chapters[c] };
  const nb = books[b + delta];
  if (!nb) return null;
  return { book: nb.book, chapter: delta > 0 ? nb.chapters[0] : nb.chapters[nb.chapters.length - 1] };
}

/** Route lue dans le fragment d'URL : "#/read/Gen/1/3" -> { page: "read", book, chapter, verse } ;
 *  "#/align" ou vide -> { page: "align" }. */
export function parseHash(hash) {
  const parts = hash.replace(/^#\/?/, "").split("/").filter(Boolean).map(decodeURIComponent);
  if (parts[0] === "read") {
    return { page: "read", book: parts[1] || null, chapter: parts[2] || null, verse: parts[3] || null };
  }
  return { page: "align" };
}

export function readHash({ book, chapter, verse }) {
  return ["#/read", ...[book, chapter, verse].filter(Boolean).map(encodeURIComponent)].join("/");
}
