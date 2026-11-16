import { useMemo, useState } from "react";
import { buildModel, related } from "../alignment.js";

/** Class and hue of a word depending on hover: highlighted, dimmed or normal. */
function look(hue, active, highlighted) {
  const style = hue === null ? undefined : { "--h": hue };
  const state = !active ? "" : highlighted ? " hl" : " dim";
  return { style, state };
}

/** Result: interlinear view and Greek text. Links shown: gdfa, i.e. sure links
 *  (inter, solid) and probable links (added by gdfa, dashed). */
export default function Alignment({ result }) {
  const [hover, setHover] = useState(null);
  const model = useMemo(() => buildModel(result, "gdfa"), [result]);
  const hl = related(model, hover);
  const leave = () => setHover(null);

  return (
    <section className="result">
      <div className="toolbar">
        <span className="meta">
          <span className="legend-sure">solid</span>: sure link ·{" "}
          <span className="legend-probable">dashed</span>: probable link
        </span>
        <span className="meta">{result.meta.aligner} · {result.meta.duration_s} s</span>
      </div>

      {result.unknown_hebrew_words.length > 0 && (
        <p className="notice">
          Words not found in the Hebrew Bible (BHSA), segmented by dictabert-seg:{" "}
          <span lang="he" dir="rtl" className="hebrew">{result.unknown_hebrew_words.join(" ")}</span>
        </p>
      )}

      <h2>Interlinear</h2>
      <div className="interlinear" dir="rtl" onMouseLeave={leave}>
        {model.words.map((w) => {
          const { style, state } = look(w.hue, hl, hl?.words.has(w.k));
          return (
            <div key={w.k} className={`word${w.greek.length ? " linked" : " unlinked"}${state}`}
              style={style} onMouseEnter={() => setHover({ side: "he", k: w.k })}>
              <div className="he" lang="he">
                {w.tokens.map((t, n) => (
                  <span key={t.i}>{n > 0 && <span className="sep">·</span>}{t.text}</span>
                ))}
              </div>
              <div className="gr" dir="ltr" lang="grc">
                {w.greek.length
                  ? w.greek.map((g) => (
                    <span key={g.j} className={g.sure ? "g sure" : "g probable"}>{g.text}</span>
                  ))
                  : <span className="none">∅</span>}
              </div>
            </div>
          );
        })}
      </div>

      <h2>Greek text</h2>
      <p className="greek-text" lang="grc" onMouseLeave={leave}>
        {model.greek.map((g) => {
          const { style, state } = look(g.hue, hl, hl?.gr.has(g.j));
          const kind = g.hue === null ? "unlinked" : g.sure ? "linked sure" : "linked probable";
          return (
            <span key={g.j} className={`token ${kind}${state}`} style={style}
              onMouseEnter={() => setHover({ side: "gr", j: g.j })}>{g.text}</span>
          );
        })}
      </p>
      <p className="hint">Hover a word to see its counterparts. Grey: word without a link.</p>
    </section>
  );
}
