import { describe, expect, it } from "vitest";
import { buildVerse, neighbour, parseHash, parseRef, readHash, related } from "./reader.js";

// Gn 1,1 réduit, tel que le renvoie /reader/Gen/1 : 3 mots pivots + setuma
const VERSE = {
  ref: "Gen.1.1",
  words: [{ text: "בְּרֵאשִׁית", graphic: true }, { text: "בָּרָא", graphic: true },
    { text: "אֶת־הַשָּׁמַיִם", graphic: true }, { text: "ס", graphic: false }],
  targets: [
    { corpus: "lxx", text: "Gen", ref: "Gen.1.1", tokens: ["ἐν", "ἀρχῇ", "ἐποίησεν", "τὸν", "οὐρανόν"],
      links: [[0, 0], [0, 1], [1, 2], [2, 3], [2, 4]], verdicts: ["juste", "juste", "faux", null] },
    { corpus: "syr", text: "Gen", ref: "Gen.1.1", tokens: ["ܒܪܫܝܬ", "ܒܪܐ", "ܝܬ", "ܫܡܝܐ", "ܘ"],
      links: [[0, 0], [1, 1], [2, 2], [2, 3]], verdicts: null },
  ],
};
const BOTH = ["lxx/Gen", "syr/Gen"];

describe("buildVerse", () => {
  it("trilingue : cellules par mot pivot et par cible", () => {
    const m = buildVerse(VERSE, BOTH);
    expect(m.words[0].cells["lxx/Gen"].map((c) => c.text)).toEqual(["ἐν", "ἀρχῇ"]);
    expect(m.words[2].cells["syr/Gen"].map((c) => c.text)).toEqual(["ܝܬ", "ܫܡܝܐ"]);
    expect(m.words[3].cells["lxx/Gen"]).toEqual([]);
    expect(m.words[2].verdicts).toEqual({ "lxx/Gen": "faux" });
  });

  it("bilingue : seules les cibles montrées", () => {
    const m = buildVerse(VERSE, ["syr/Gen"]);
    expect(m.targets.map((t) => t.key)).toEqual(["syr/Gen"]);
    expect(Object.keys(m.words[0].cells)).toEqual(["syr/Gen"]);
  });

  it("token cible sans lien : sans couleur", () => {
    const m = buildVerse(VERSE, BOTH);
    expect(m.targets[1].tokens[4]).toMatchObject({ text: "ܘ", tone: null });
    expect(m.targets[0].tokens[1].tone).toBe(m.words[0].tone);
  });
});

describe("related", () => {
  it("mot hébreu : ses correspondants dans les deux cibles", () => {
    const r = related(buildVerse(VERSE, BOTH), { w: 2 });
    expect([...r.words]).toEqual([2]);
    expect([...r.tokens["lxx/Gen"]]).toEqual([3, 4]);
    expect([...r.tokens["syr/Gen"]]).toEqual([2, 3]);
  });

  it("token grec : l'hébreu en pivot vers le syriaque", () => {
    const r = related(buildVerse(VERSE, BOTH), { key: "lxx/Gen", j: 1 });
    expect([...r.words]).toEqual([0]);
    expect([...r.tokens["lxx/Gen"]].sort()).toEqual([0, 1]);
    expect([...r.tokens["syr/Gen"]]).toEqual([0]);
  });

  it("token sans lien : lui seul", () => {
    const r = related(buildVerse(VERSE, BOTH), { key: "syr/Gen", j: 4 });
    expect(r.words.size).toBe(0);
    expect([...r.tokens["syr/Gen"]]).toEqual([4]);
  });
});

describe("navigation", () => {
  const BOOKS = [{ book: "Gen", chapters: ["1", "2"] }, { book: "Exod", chapters: ["1", "2", "3"] },
    { book: "1Sam", chapters: ["1"] }];
  const names = BOOKS.map((b) => b.book);

  it("références saisies", () => {
    expect(parseRef("Gen.1.3", names)).toEqual({ book: "Gen", chapter: "1", verse: "3" });
    expect(parseRef("exod 2:4", names)).toEqual({ book: "Exod", chapter: "2", verse: "4" });
    expect(parseRef("1 Sam 1", names)).toEqual({ book: "1Sam", chapter: "1", verse: null });
    expect(parseRef("Matt 1", names)).toBeNull();
  });

  it("chapitre voisin, d'un livre à l'autre", () => {
    expect(neighbour(BOOKS, "Gen", "2", 1)).toEqual({ book: "Exod", chapter: "1" });
    expect(neighbour(BOOKS, "Exod", "1", -1)).toEqual({ book: "Gen", chapter: "2" });
    expect(neighbour(BOOKS, "Gen", "1", -1)).toBeNull();
  });

  it("fragment d'URL", () => {
    expect(parseHash("#/read/Gen/1/3")).toEqual({ page: "read", book: "Gen", chapter: "1", verse: "3" });
    expect(parseHash("")).toEqual({ page: "align" });
    expect(readHash({ book: "Gen", chapter: "1", verse: null })).toBe("#/read/Gen/1");
  });
});
