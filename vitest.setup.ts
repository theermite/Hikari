/// <reference types="@testing-library/jest-dom" />
//
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

// jsdom n'implémente ni `showModal()` ni `close()` sur `<dialog>` (constaté 2026-08-19,
// jsdom 30.0.1 — `HTMLDialogElement.showModal is not a function`). Modal.tsx s'appuie sur
// le natif : sans ce palliatif, toute fenêtre modale plante au montage sous jsdom, réel ou
// non. Le palliatif suit le comportement observable que les tests interrogent (l'attribut
// `open`), pas la gestion complète de la couche supérieure du navigateur.
if (typeof HTMLDialogElement !== "undefined") {
  HTMLDialogElement.prototype.showModal ??= function (
    this: HTMLDialogElement,
  ) {
    this.setAttribute("open", "");
  };
  HTMLDialogElement.prototype.close ??= function (this: HTMLDialogElement) {
    this.removeAttribute("open");
  };
}
