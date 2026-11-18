import { useEffect, useState } from "react";
import AlignPage from "./components/AlignPage.jsx";
import ReaderPage from "./components/ReaderPage.jsx";
import logo from "./assets/logo-dark.png";     // version claire du logo, pour la barre foncée
import { parseHash, readHash } from "./reader.js";

const REPOSITORY = "https://github.com/metz-theolab/polyglot-align";

/** GitHub mark (Octicons, MIT). */
function GitHubIcon() {
  return (
    <svg viewBox="0 0 16 16" width="22" height="22" aria-hidden="true" fill="currentColor">
      <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z" />
    </svg>
  );
}

/** App bar with the two modes (Align, Read) ; route in the URL fragment
 *  (#/align, #/read/Gen/1/3). Both pages stay mounted: switching mode keeps
 *  the typed texts and the reading position. */
export default function App() {
  const [route, setRoute] = useState(() => parseHash(window.location.hash));
  const [lastRead, setLastRead] = useState(null);

  useEffect(() => {
    const onHash = () => setRoute(parseHash(window.location.hash));
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  useEffect(() => {
    if (route.page === "read" && route.book) setLastRead(route);
  }, [route]);

  return (
    <>
      <nav className="appbar">
        <a className="brand" href="#/align">
          <img src={logo} alt="polyglot-align" height="24" />
        </a>
        <div className="bar-right">
          <div className="tabs" role="tablist">
            <a role="tab" href="#/align" aria-selected={route.page === "align"}
              className={route.page === "align" ? "tab on" : "tab"}>Align</a>
            <a role="tab" href={lastRead ? readHash(lastRead) : "#/read"} aria-selected={route.page === "read"}
              className={route.page === "read" ? "tab on" : "tab"}>Read</a>
          </div>
          <a className="github" href={REPOSITORY} target="_blank" rel="noreferrer"
            title="Source code on GitHub" aria-label="Source code on GitHub"><GitHubIcon /></a>
        </div>
      </nav>
      <div hidden={route.page !== "align"}><AlignPage /></div>
      <div hidden={route.page !== "read"}>
        <ReaderPage route={route.page === "read" ? route : lastRead} active={route.page === "read"} />
      </div>
      <footer className="footer">© 2026 Frédérique Michèle Rey</footer>
    </>
  );
}
