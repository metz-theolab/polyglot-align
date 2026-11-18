import { useEffect, useState } from "react";
import * as api from "../api.js";
import AlignForm from "./AlignForm.jsx";
import Alignment from "./Alignment.jsx";

/** Align mode: API status, input of two texts, result. */
export default function AlignPage() {
  const [status, setStatus] = useState({ status: "loading" });
  const [algorithms, setAlgorithms] = useState([{ name: "eflomal", label: "eflomal", status: "loading" }]);
  const [algorithm, setAlgorithm] = useState("eflomal");
  const [hebrew, setHebrew] = useState("");
  const [greek, setGreek] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);

  // model status: polled every 2 s while the models are loading
  useEffect(() => {
    let stop = false;
    let timer;
    const poll = async () => {
      try {
        const h = await api.health();
        if (stop) return;
        setStatus(h);
        if (h.status === "ready") {
          // algorithms offered by the backend; polled while one is still loading
          const i = await api.info();
          if (stop) return;
          setAlgorithms(i.algorithms);
          setAlgorithm((current) => i.algorithms.some((a) => a.name === current && a.status === "ready")
            ? current : i.default);
          if (!i.algorithms.some((a) => a.status === "loading")) return;
          timer = setTimeout(poll, 5000);
          return;
        }
        if (h.status === "error") return;
      } catch (e) {
        if (!stop) setStatus({ status: "unreachable", detail: e.message });
      }
      timer = setTimeout(poll, 2000);
    };
    poll();
    return () => { stop = true; clearTimeout(timer); };
  }, []);

  const submit = async () => {
    setBusy(true);
    setError(null);
    try {
      setResult(await api.align(hebrew, greek, algorithm));
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="page">
      <header>
        <p className="subtitle">Word alignment of a Hebrew text and a Greek text</p>
        <Status status={status} />
      </header>

      <AlignForm hebrew={hebrew} greek={greek} setHebrew={setHebrew} setGreek={setGreek}
        algorithms={algorithms} algorithm={algorithm} setAlgorithm={setAlgorithm}
        ready={status.status === "ready"} busy={busy} onSubmit={submit} />

      {busy && <p className="busy">{BUSY[algorithm] || "Aligning…"}</p>}
      {error && <p className="error">{error}</p>}
      {result && <Alignment result={result} />}
    </div>
  );
}

const BUSY = {
  eflomal: "Training eflomal on the Bible and your text (a few seconds)…",
  simalign: "Computing contextual embeddings…",
  llm: "Asking the language model (up to a minute)…",
};

function Status({ status }) {
  const text = {
    loading: "Loading models…",
    ready: "Ready",
    error: `Models could not be loaded: ${status.detail}`,
    unreachable: status.detail,
  }[status.status];
  return <p className={`status ${status.status}`}>{text}</p>;
}
