// Chargé pour chaque fichier de test, quel que soit son environnement.
//
// `IS_REACT_ACT_ENVIRONMENT` élimine un avertissement connu et sans rapport avec une
// vraie rupture React 19 / Testing Library — juste une ligne de configuration oubliée
// (veille 2026-08-19, voir vite.config.ts). Sans effet sur les tests de logique pure
// (environnement `node`) : React n'y est jamais rendu.
// @ts-expect-error — global d'exécution React, non typé côté public
globalThis.IS_REACT_ACT_ENVIRONMENT = true;

import "@testing-library/jest-dom/vitest";

// jsdom n'implémente pas ResizeObserver (lacune connue, pas un bug de configuration).
// dockview (le système de panneaux du cockpit) l'utilise pour mesurer ses grilles ; sans
// palliatif, tout composant monté à travers Cockpit fait planter jsdom à l'instant du
// montage. Un bouchon muet suffit — aucun test n'a besoin de vraies mesures de disposition.
if (typeof globalThis.ResizeObserver === "undefined") {
  globalThis.ResizeObserver = class {
    observe() {}
    unobserve() {}
    disconnect() {}
  };
}
