import { memo, useMemo, useState } from "react";
import { toneStyle } from "../alignment.js";
import { buildVerse, readHash, related } from "../reader.js";

const NAME = { lxx: "LXX", syr: "Peshitta" };
const LANG = { lxx: "grc", syr: "syc" };

// verdict of the CATSS gold (review CSV) -> CSS class
const VERDICT = { juste: "v-ok", "ok (minus)": "v-ok", faux: "v-bad", "non aligné": "v-miss", "?": "v-unk" };

/** Class and colour of a word or token depending on hover: highlighted, dimmed or normal. */
function look(tone, active, highlighted) {
  const style = toneStyle(tone);
  const state = !active ? "" : highlighted ? " hl" : " dim";
  return { style, state };
}

/** One verse: interlinear (Hebrew pivot word, then its counterparts in each
 *  shown text), then each text in its own order. */
function VerseView({ verse, shown, corpora, gold, current }) {
  const [hover, setHover] = useState(null);
  const model = useMemo(() => buildVerse(verse, shown), [verse, shown]);
  const hl = related(model, hover);
  const leave = () => setHover(null);
  const [book, chapter, n] = verse.ref.split(".");
  const meta = (t) => corpora[t.corpus] || {};

  return (
    <article className={current ? "verse current" : "verse"} id={`v-${n}`}>
      <a className="vnum" href={readHash({ book, chapter, verse: n })} title={verse.ref}>{n}</a>
      <div className="vbody">
        <div className="interlinear" dir="rtl" onMouseLeave={leave}>
          {model.words.map((w) => {
            if (!w.graphic) return <span key={w.w} className="mark" lang="he">{w.text}</span>;
            const linked = model.targets.some((t) => w.cells[t.key].length);
            const { style, state } = look(linked ? w.tone : null, hl, hl?.words.has(w.w));
            return (
              <div key={w.w} className={`word${linked ? " linked" : " unlinked"}${state}`} style={style}
                onMouseEnter={() => setHover({ w: w.w })}>
                <div className="he" lang="he">{w.text}</div>
                {model.targets.map((t) => {
                  const m = meta(t);
                  const verdict = gold && m.gold ? VERDICT[w.verdicts[t.key]] || "" : "";
                  return (
                    <div key={t.key} className={`cell ${m.target} ${verdict}`} dir={m.direction}
                      lang={LANG[m.target]}>
                      {w.cells[t.key].length
                        ? w.cells[t.key].map((c) => <span key={c.j}>{c.text}</span>)
                        : <span className="none">∅</span>}
                    </div>
                  );
                })}
              </div>
            );
          })}
        </div>

        {model.targets.map((t) => {
          const m = meta(t);
          return (
            <p key={t.key} className={`target-text ${m.target}`} dir={m.direction} lang={LANG[m.target]}
              onMouseLeave={leave}>
              <span className="tlabel" dir="ltr">
                {NAME[m.target]}{t.text !== book ? ` (${t.text})` : ""}{t.ref !== verse.ref ? ` ${t.ref.split(".").slice(1).join(":")}` : ""}
              </span>
              {t.tokens.map((tok) => {
                const { style, state } = look(tok.tone, hl, hl?.tokens[t.key]?.has(tok.j));
                return (
                  <span key={tok.j} className={`token ${tok.tone === null ? "unlinked" : "linked"}${state}`}
                    style={style} onMouseEnter={() => setHover({ key: t.key, j: tok.j })}>{tok.text}</span>
                );
              })}
            </p>
          );
        })}
        {!model.targets.length && shown.length > 0 && (
          <p className="hint">No counterpart in the aligned texts for this verse.</p>
        )}
      </div>
    </article>
  );
}

export default memo(VerseView);
