// Calculs de la vue d'alignement, sans React (testés par alignment.test.js).
//
// Réponse de l'API (POST /api/v1/align) :
//   hebrew / greek : { text, tokens: [...], graphic: [n° du mot graphique de chaque token] }
//   links : { sure: [[i, j], ...], all: [[i, j], ...] }   i : token hébreu, j : token grec
// sure (liens sûrs) est toujours inclus dans all (sûrs + probables), quel que
// soit l'algorithme (eflomal : inter / gdfa ; SimAlign : argmax / itermax ;
// LLM : un seul niveau).

/** Couleurs des mots reliés : Veiled Vista, Baltic Sea, Golden Mist, Quiet
 *  Violet (palette du site, styles.css : --tone-0 … --tone-3). */
export const TONES = 4;

/** Couleur (0 à TONES - 1) du k-ième mot hébreu : à tour de rôle, deux
 *  voisins n'ont jamais la même. */
export function tone(k) {
  return k % TONES;
}

/** Style d'un mot coloré : sa couleur de palette en variable CSS --c. */
export function toneStyle(t) {
  return t === null ? undefined : { "--c": `var(--tone-${t})` };
}

/**
 * Modèle d'affichage d'un alignement : tous les liens (all), les sûrs marqués.
 * - words : mots graphiques hébreux dans l'ordre du texte,
 *   { k, tone, tokens: [{ i, text }], greek: [{ j, text, sure }] }
 * - greek : tokens grecs dans l'ordre, { j, text, tone (null si sans lien), sure }
 * - heToGr, grToHe : liens dans les deux sens (Map indice -> [indices])
 * - wordOf : n° du mot graphique de chaque token hébreu
 */
export function buildModel(result) {
  const sure = new Set(result.links.sure.map(([i, j]) => `${i}-${j}`));
  const links = result.links.all.map(([i, j]) => ({
    i, j, sure: sure.has(`${i}-${j}`),
  }));

  const heToGr = new Map();
  const grToHe = new Map();
  for (const { i, j } of links) {
    if (!heToGr.has(i)) heToGr.set(i, []);
    if (!grToHe.has(j)) grToHe.set(j, []);
    heToGr.get(i).push(j);
    grToHe.get(j).push(i);
  }

  const wordOf = result.hebrew.graphic;
  const order = [];
  const byWord = new Map();
  result.hebrew.tokens.forEach((text, i) => {
    const k = wordOf[i];
    if (!byWord.has(k)) {
      byWord.set(k, { k, tone: tone(order.length), tokens: [], greek: new Map() });
      order.push(k);
    }
    const word = byWord.get(k);
    word.tokens.push({ i, text });
    for (const { i: a, j, sure: s } of links) {
      if (a !== i) continue;
      const prev = word.greek.get(j);
      word.greek.set(j, { j, text: result.greek.tokens[j], sure: s || Boolean(prev?.sure) });
    }
  });
  const words = order.map((k) => {
    const w = byWord.get(k);
    return { ...w, greek: [...w.greek.values()].sort((a, b) => a.j - b.j) };
  });

  // couleur d'un mot grec : celle du premier mot hébreu (dans l'ordre du texte) qui lui est relié
  const toneOfWord = new Map(words.map((w) => [w.k, w.tone]));
  const greek = result.greek.tokens.map((text, j) => {
    const hes = grToHe.get(j) || [];
    if (!hes.length) return { j, text, tone: null, sure: false };
    const first = Math.min(...hes.map((i) => order.indexOf(wordOf[i])));
    const s = links.some((l) => l.j === j && l.sure);
    return { j, text, tone: toneOfWord.get(order[first]), sure: s };
  });

  return { words, greek, heToGr, grToHe, wordOf };
}

/**
 * Ce qu'il faut surligner quand on survole :
 * - un mot hébreu (hover = { side: "he", k }) : ses tokens et tous les grecs reliés ;
 * - un mot grec (hover = { side: "gr", j }) : lui, les tokens hébreux reliés et leurs mots.
 * Renvoie { he: Set(i), gr: Set(j), words: Set(k) }, ou null si rien n'est survolé.
 */
export function related(model, hover) {
  if (!hover) return null;
  const he = new Set();
  const gr = new Set();
  const words = new Set();
  if (hover.side === "he") {
    words.add(hover.k);
    model.wordOf.forEach((k, i) => {
      if (k !== hover.k) return;
      he.add(i);
      (model.heToGr.get(i) || []).forEach((j) => gr.add(j));
    });
  } else {
    gr.add(hover.j);
    (model.grToHe.get(hover.j) || []).forEach((i) => {
      he.add(i);
      words.add(model.wordOf[i]);
    });
  }
  return { he, gr, words };
}
