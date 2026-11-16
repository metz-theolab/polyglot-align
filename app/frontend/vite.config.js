import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

// Le front appelle l'API par des chemins relatifs (/api/v1/…) : aucune adresse
// écrite en dur. En développement, le serveur Vite les renvoie vers le backend
// (VITE_API_TARGET, défaut http://127.0.0.1:8000). Voir decisions-app.md.
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const target = env.VITE_API_TARGET || "http://127.0.0.1:8000";
  return {
    plugins: [react()],
    server: { proxy: { "/api": target } },
    preview: { proxy: { "/api": target } },
    test: { environment: "node" },
  };
});
