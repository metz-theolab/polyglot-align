import { describe, expect, it } from "vitest";
import { buildModel, hue, related } from "./alignment.js";

// Gn 1:1 (début) tel que le renvoie l'API : בְּ·רֵאשִׁית = un mot graphique (n° 0)
const RESULT = {
  hebrew: { tokens: ["בְּ", "רֵאשִׁית", "בָּרָא", "אֱלֹהִים"], graphic: [0, 0, 1, 2] },
  greek: { tokens: ["ἐν", "ἀρχῇ", "ἐποίησεν", "ὁ", "θεὸς"], graphic: [0, 1, 2, 3, 4] },
  links: {
    inter: [[0, 0], [1, 1], [2, 2], [3, 4]],
    gdfa: [[0, 0], [1, 1], [2, 2], [3, 3], [3, 4]],
  },
};

describe("buildModel", () => {
  it("regroupe les tokens hébreux par mot graphique, dans l'ordre du texte", () => {
    const m = buildModel(RESULT, "inter");
    expect(m.words.map((w) => w.tokens.map((t) => t.text))).toEqual([["בְּ", "רֵאשִׁית"], ["בָּרָא"], ["אֱלֹהִים"]]);
    expect(m.words[0].greek.map((g) => g.text)).toEqual(["ἐν", "ἀρχῇ"]);
  });

  it("inter : liens sûrs seulement ; ὁ sans lien", () => {
    const m = buildModel(RESULT, "inter");
    expect(m.words[2].greek.map((g) => g.text)).toEqual(["θεὸς"]);
    expect(m.greek[3]).toMatchObject({ text: "ὁ", hue: null });
  });

  it("gdfa : ajoute les liens probables, marqués non sûrs", () => {
    const m = buildModel(RESULT, "gdfa");
    expect(m.words[2].greek).toEqual([
      { j: 3, text: "ὁ", sure: false },
      { j: 4, text: "θεὸς", sure: true },
    ]);
    expect(m.greek[3].sure).toBe(false);
  });

  it("un mot grec prend la teinte du mot hébreu relié", () => {
    const m = buildModel(RESULT, "inter");
    expect(m.greek[0].hue).toBe(m.words[0].hue);
    expect(m.greek[4].hue).toBe(m.words[2].hue);
  });
});

describe("hue", () => {
  it("donne des teintes voisines distinctes", () => {
    const hues = [0, 1, 2, 3, 4, 5].map(hue);
    expect(new Set(hues).size).toBe(6);
    expect(Math.abs(hues[1] - hues[0])).toBeGreaterThan(60);
  });
});

describe("related", () => {
  const m = buildModel(RESULT, "gdfa");

  it("survol d'un mot hébreu : ses tokens et les mots grecs reliés", () => {
    const r = related(m, { side: "he", k: 0 });
    expect([...r.he]).toEqual([0, 1]);
    expect([...r.gr].sort()).toEqual([0, 1]);
  });

  it("survol d'un mot grec : les tokens hébreux reliés et leurs mots", () => {
    const r = related(m, { side: "gr", j: 3 });
    expect([...r.he]).toEqual([3]);
    expect([...r.words]).toEqual([2]);
  });

  it("rien de survolé : null", () => {
    expect(related(m, null)).toBeNull();
  });
});
