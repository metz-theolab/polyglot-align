import { useEffect, useState } from "react";
import * as api from "./api.js";
import AlignForm from "./components/AlignForm.jsx";
import Alignment from "./components/Alignment.jsx";

/** Single page: API status, input, result. */
export default function App() {
  const [status, setStatus] = useState({ status: "loading" });
  const [algorithms, setAlgorithms] = useState(["eflomal"]);
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
          const i = await api.info();          // algorithms offered by the backend
          if (!stop) { setAlgorithms([i.aligner]); setAlgorithm(i.aligner); }
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
      setResult(await api.align(hebrew, greek));
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="page">
      <header>
        <h1>polyglot-align</h1>
        <p className="subtitle">Word alignment of a Hebrew text and a Greek text</p>
        <Status status={status} />
      </header>

      <AlignForm hebrew={hebrew} greek={greek} setHebrew={setHebrew} setGreek={setGreek}
        algorithms={algorithms} algorithm={algorithm} setAlgorithm={setAlgorithm}
        ready={status.status === "ready"} busy={busy} onSubmit={submit} />

      {busy && <p className="busy">Training eflomal on the Bible and your text (a few seconds)…</p>}
      {error && <p className="error">{error}</p>}
      {result && <Alignment result={result} />}
    </div>
  );
}

function Status({ status }) {
  const text = {
    loading: "Loading models…",
    ready: "Ready",
    error: `Models could not be loaded: ${status.detail}`,
    unreachable: status.detail,
  }[status.status];
  return <p className={`status ${status.status}`}>{text}</p>;
}
