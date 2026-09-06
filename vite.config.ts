/// <reference types="vitest/config" />
import { readFileSync } from "node:fs";
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// @ts-expect-error process is a nodejs global
const host = process.env.TAURI_DEV_HOST;

// La version affichée dans le cockpit vient du fichier qui décide de la version INSTALLÉE.
// Lue ici, à la construction : une constante ne peut pas échouer à l'exécution et laisser
// la case vide, là où un appel au système le pourrait. Et comme c'est le même fichier que
// celui du paquet, l'écran ne peut pas annoncer une version que l'app n'a pas.
const appVersion = JSON.parse(
  readFileSync(new URL("./src-tauri/tauri.conf.json", import.meta.url), "utf-8"),
).version as string;

// https://vite.dev/config/
export default defineConfig(async () => ({
  plugins: [react(), tailwindcss()],

  define: { __APP_VERSION__: JSON.stringify(appVersion) },

  // Options Vite adaptées à Tauri (appliquées en `tauri dev` / `tauri build`).
  clearScreen: false, // 1. ne pas masquer les erreurs Rust
  server: {
    port: 1420, // 2. Tauri attend un port fixe
    strictPort: true,
    // Épinglé sur la boucle locale IPv4, jamais laissé au choix du serveur.
    // Vécu 2026-08-05 : avec `false`, Vite n'écoutait QUE en IPv6 (`::1`). La fenêtre de
    // l'app charge `localhost`, qui se résout tantôt en IPv6 tantôt en IPv4 ; quand elle
    // tombait sur l'IPv4, la connexion était refusée et l'app restait BLANCHE, sans la
    // moindre erreur dans les journaux. Cette adresse écoute les deux familles utiles ici.
    host: host || "127.0.0.1",
    hmr: host ? { protocol: "ws", host, port: 1421 } : undefined,
    watch: {
      ignored: ["**/src-tauri/**"], // 3. ne pas surveiller src-tauri
    },
  },

  // Vitest — garde-fous d'hygiène (Quality.md : forks bornés, isolation, timeouts).
  test: {
    // Ne jamais exécuter les tests des worktrees d'agents (branches en cours de revue) :
    // ils embarquent leur propre copie du code et feraient échouer le suite de `main`.
    exclude: ["**/node_modules/**", "**/dist/**", "**/.claude/worktrees/**"],
    // `node` par défaut (rapide, suffit à toute la logique pure). Un fichier de test de
    // composant demande jsdom explicitement via `// @vitest-environment jsdom` en tête —
    // ainsi le socle reste inchangé pour les 142 tests de logique existants (2026-08-19).
    environment: "node",
    // React n'expose `act` que dans sa construction de DÉVELOPPEMENT. Quand la variable
    // NODE_ENV de la machine vaut « production » (vécu 2026-09-06 : elle était posée dans
    // l'environnement de la session), React résout sa construction de production et 63
    // tests de composants tombent sur « React.act is not a function » — sans qu'une seule
    // ligne du dépôt ait changé. On épingle donc la valeur ici : la suite ne dépend plus
    // de ce que la machine a dans son environnement.
    env: { NODE_ENV: "test" },
    setupFiles: ["./vitest.setup.ts"],
    globals: true,
    // `poolOptions.forks.maxForks` a fusionné en `maxWorkers` top-level dans Vitest 4 —
    // dépréciation constatée et corrigée le 2026-08-19 en posant cette configuration
    // (veille : vitest.dev/guide/migration#pool-rework). Même comportement, syntaxe à plat.
    pool: "forks",
    maxWorkers: 2,
    isolate: true,
    maxConcurrency: 5,
    testTimeout: 10000,
    hookTimeout: 10000,
  },
}));
