import { useEffect, useMemo, useState } from "react";
import * as api from "../api.js";
import { neighbour, parseRef, readHash, targetKey } from "../reader.js";
import VerseView from "./VerseView.jsx";

const LANGUAGE = { lxx: "Greek", syr: "Syriac" };
const SETTINGS = "polyglot-reader";

function loadSettings() {
  try {
    return JSON.parse(localStorage.getItem(SETTINGS)) || {};
  } catch {
    return {};
  }
}

function saveSettings(settings) {
  try {
    localStorage.setItem(SETTINGS, JSON.stringify(settings));
  } catch { /* storage unavailable: settings not remembered */ }
}

const go = (route) => { window.location.hash = readHash(route); };

/** Read mode: texts already aligned (results/), Hebrew as pivot, one chapter
 *  at a time; Greek / Syriac toggles (trilingual or bilingual view). */
export default function ReaderPage({ route, active }) {
  const [corpora, setCorpora] = useState(null);
  const [books, setBooks] = useState(null);
  const [chapter, setChapter] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);
  const [settings, setSettings] = useState(loadSettings);   // { hidden: [ids], gold, texts: {id: text} }
  const [jump, setJump] = useState("");

  const update = (patch) => setSettings((s) => {
    const next = { ...s, ...patch };
    saveSettings(next);
    return next;
  });

  // catalogue: once, when the mode is first opened
  useEffect(() => {
    if (!active || corpora) return;
    Promise.all([api.readerCorpora(), api.readerBooks()])
      .then(([c, b]) => { setCorpora(c); setBooks(b); })
      .catch((e) => setError(e.message));
  }, [active, corpora]);

  // no passage in the URL: first chapter of the first book
  useEffect(() => {
    if (active && books?.length && !route?.book) {
      window.location.replace(readHash({ book: books[0].book, chapter: books[0].chapters[0] }));
    }
  }, [active, books, route]);

  const book = route?.book;
  const ch = route?.chapter;
  useEffect(() => {
    if (!book || !ch) return;
    let stop = false;
    setLoading(true);
    setError(null);
    api.readerChapter(book, ch)
      .then((data) => { if (!stop) setChapter(data); })
      .catch((e) => { if (!stop) { setError(e.message); setChapter(null); } })
      .finally(() => { if (!stop) setLoading(false); });
    return () => { stop = true; };
  }, [book, ch]);

  // verse in the URL: scroll to it once the chapter is shown
  const verse = route?.verse;
  useEffect(() => {
    if (active && chapter && verse) {
      const scroll = () => document.getElementById(`v-${verse}`)?.scrollIntoView({ block: "start" });
      scroll();
      document.fonts?.ready.then(scroll);      // the fonts change the height of the verses above
    }
  }, [active, chapter, verse]);

  const entry = books?.find((b) => b.book === book);
  const byId = useMemo(() => Object.fromEntries((corpora || []).map((c) => [c.id, c])), [corpora]);
  const hidden = settings.hidden || [];

  // shown texts: one per visible corpus; several texts for this book (Judg / JudgA): the chosen one
  const choices = {};
  for (const t of entry?.texts || []) (choices[t.corpus] ||= []).push(t.text);
  const shownKey = Object.entries(choices)
    .filter(([id]) => !hidden.includes(id))
    .map(([id, texts]) => {
      const chosen = settings.texts?.[id];
      return targetKey({ corpus: id, text: texts.includes(chosen) ? chosen : texts[0] });
    }).join("|");
  // same array while the choice is unchanged: verses are memoized
  const shown = useMemo(() => (shownKey ? shownKey.split("|") : []), [shownKey]);
  const goldOn = Boolean(settings.gold) && shown.some((k) => byId[k.split("/")[0]]?.gold);

  const toggle = (id) => update({ hidden: hidden.includes(id) ? hidden.filter((x) => x !== id) : [...hidden, id] });
  const prev = books && book && neighbour(books, book, ch, -1);
  const next = books && book && neighbour(books, book, ch, 1);

  const submitJump = (e) => {
    e.preventDefault();
    const ref = parseRef(jump, (books || []).map((b) => b.book));
    if (!ref) {
      setError(`unknown reference: ${jump} (e.g. Gen 1:3, Ps 23)`);
      return;
    }
    setError(null);
    setJump("");
    go(ref);
  };

  return (
    <div className="page reader">
      <div className="reader-bar">
        <div className="nav">
          <button type="button" className="secondary icon" disabled={!prev} onClick={() => go(prev)}
            aria-label="previous chapter" title="previous chapter">‹</button>
          <select aria-label="book" value={book || ""}
            onChange={(e) => go({ book: e.target.value, chapter: books.find((b) => b.book === e.target.value).chapters[0] })}>
            {(books || []).map((b) => <option key={b.book} value={b.book}>{b.book}</option>)}
          </select>
          <select aria-label="chapter" value={ch || ""} onChange={(e) => go({ book, chapter: e.target.value })}>
            {(entry?.chapters || []).map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
          <button type="button" className="secondary icon" disabled={!next} onClick={() => go(next)}
            aria-label="next chapter" title="next chapter">›</button>
          <form onSubmit={submitJump} className="jump">
            <input value={jump} onChange={(e) => setJump(e.target.value)} placeholder="Go to… Gen 1:3"
              aria-label="go to reference" />
          </form>
        </div>
        <div className="nav">
          {(corpora || []).map((c) => (
            <button key={c.id} type="button" aria-pressed={!hidden.includes(c.id)}
              className={hidden.includes(c.id) ? "toggle" : "toggle on"} onClick={() => toggle(c.id)}
              title={c.label}>{LANGUAGE[c.target] || c.target}</button>
          ))}
          {(corpora || []).some((c) => c.gold) && (
            <button type="button" aria-pressed={Boolean(settings.gold)}
              className={settings.gold ? "toggle on" : "toggle"} onClick={() => update({ gold: !settings.gold })}
              title="colour links by the CATSS gold verdict (Greek only)">Gold</button>
          )}
          {Object.entries(choices).filter(([id, texts]) => texts.length > 1 && !hidden.includes(id)).map(([id, texts]) => (
            <select key={id} aria-label={`${LANGUAGE[byId[id]?.target]} text`}
              value={shown.find((k) => k.startsWith(id + "/")).split("/")[1]}
              onChange={(e) => update({ texts: { ...settings.texts, [id]: e.target.value } })}>
              {texts.map((t) => <option key={t} value={t}>{LANGUAGE[byId[id]?.target]}: {t}</option>)}
            </select>
          ))}
        </div>
      </div>

      {goldOn && (
        <p className="legend">
          Gold (CATSS):{" "}
          <span className="cell v-ok">correct</span>
          <span className="cell v-bad">wrong</span>
          <span className="cell v-miss">missing link</span>
          <span className="cell v-unk">not in gold</span>
        </p>
      )}
      {error && <p className="error">{error}</p>}
      {loading && <p className="busy">Loading {book} {ch}…</p>}

      {chapter && (
        <div className={loading ? "verses stale" : "verses"}>
          <h2 className="chapter-title">{chapter.book} {chapter.chapter}</h2>
          {chapter.verses.map((v) => (
            <VerseView key={v.ref} verse={v} shown={shown} corpora={byId} gold={goldOn}
              current={v.ref === `${book}.${ch}.${verse}`} />
          ))}
        </div>
      )}
      {active && <p className="hint">Hover a word to see its counterparts in every text.
        Grey: word without a link. Links: {(corpora || [])[0]?.method || "gdfa"} (eflomal).</p>}
    </div>
  );
}
