// Calculs de la vue d'alignement, sans React (testés par alignment.test.js).
//
// Réponse de l'API (POST /api/v1/align) :
//   hebrew / greek : { text, tokens: [...], graphic: [n° du mot graphique de chaque token] }
//   links : { inter: [[i, j], ...], gdfa: [[i, j], ...] }   i : token hébreu, j : token grec
// inter (liens sûrs) est toujours inclus dans gdfa (sûrs + probables).

/** Teinte (0-360) du k-ième mot graphique hébreu : angle d'or, voisins bien distincts. */
export function hue(k) {
  return Math.round((k * 137.508) % 360);
}

/**
 * Modèle d'affichage d'un alignement pour un mode ("inter" ou "gdfa").
 * - words : mots graphiques hébreux dans l'ordre du texte,
 *   { k, hue, tokens: [{ i, text }], greek: [{ j, text, sure }] }
 * - greek : tokens grecs dans l'ordre, { j, text, hue (null si sans lien), sure }
 * - heToGr, grToHe : liens dans les deux sens (Map indice -> [indices])
 * - wordOf : n° du mot graphique de chaque token hébreu
 */
export function buildModel(result, mode = "inter") {
  const sure = new Set(result.links.inter.map(([i, j]) => `${i}-${j}`));
  const links = (mode === "gdfa" ? result.links.gdfa : result.links.inter).map(([i, j]) => ({
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
      byWord.set(k, { k, hue: hue(order.length), tokens: [], greek: new Map() });
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
  const hueOfWord = new Map(words.map((w) => [w.k, w.hue]));
  const greek = result.greek.tokens.map((text, j) => {
    const hes = grToHe.get(j) || [];
    if (!hes.length) return { j, text, hue: null, sure: false };
    const first = Math.min(...hes.map((i) => order.indexOf(wordOf[i])));
    const s = links.some((l) => l.j === j && l.sure);
    return { j, text, hue: hueOfWord.get(order[first]), sure: s };
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
