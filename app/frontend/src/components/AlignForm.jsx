import EXAMPLES from "../examples.js";

/** Input of the two texts, algorithm choice, examples. */
export default function AlignForm({ hebrew, greek, setHebrew, setGreek, algorithms, algorithm,
  setAlgorithm, ready, busy, onSubmit }) {
  const submit = (e) => {
    e.preventDefault();
    onSubmit();
  };
  const pick = (e) => {
    const example = EXAMPLES[Number(e.target.value)];
    if (example) {
      setHebrew(example.hebrew);
      setGreek(example.greek);
    }
    e.target.value = "";            // the menu goes back to « Examples… »
  };
  return (
    <form className="form" onSubmit={submit}>
      <label className="field">
        <span className="label">Text A — Hebrew (pointed or not)</span>
        <textarea dir="rtl" lang="he" className="hebrew" rows={3} value={hebrew}
          onChange={(e) => setHebrew(e.target.value)} placeholder="בְּרֵאשִׁית בָּרָא אֱלֹהִים…" />
      </label>
      <label className="field">
        <span className="label">Text B — Greek</span>
        <textarea lang="grc" className="greek" rows={3} value={greek}
          onChange={(e) => setGreek(e.target.value)} placeholder="ἐν ἀρχῇ ἐποίησεν ὁ θεὸς…" />
      </label>
      <div className="actions">
        <label className="inline">
          <span className="label">Algorithm</span>
          <select value={algorithm} onChange={(e) => setAlgorithm(e.target.value)}>
            {algorithms.map((a) => (
              <option key={a.name} value={a.name} disabled={a.status !== "ready"} title={a.detail || ""}>
                {a.label}{a.status === "loading" ? " (loading…)" : a.status === "unavailable" ? " (unavailable)" : ""}
              </option>
            ))}
          </select>
        </label>
        <label className="inline">
          <span className="label">Examples</span>
          <select defaultValue="" onChange={pick}>
            <option value="" disabled>Choose a verse…</option>
            {EXAMPLES.map((ex, n) => <option key={ex.label} value={n}>{ex.label}</option>)}
          </select>
        </label>
        <button type="submit" disabled={!ready || busy || !hebrew.trim() || !greek.trim()}>
          {busy ? "Aligning…" : "Align"}
        </button>
      </div>
    </form>
  );
}
