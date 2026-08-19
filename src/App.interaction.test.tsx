// @vitest-environment jsdom
//
// Preuve que jsdom + React Testing Library tournent avec React 19.2.7 (veille 2026-08-19,
// voir vite.config.ts). Le blocage documenté dans App.test.tsx datait de fin 2024, réglé
// depuis dans @testing-library/react v16.1.0 — ce fichier est la preuve d'exécution, pas
// juste l'affirmation.

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import App from "./App";

afterEach(() => {
  cleanup();
});

describe("App shell (jsdom + Testing Library)", () => {
  it("should_render_with_a_real_dom_under_react_19", () => {
    render(<App />);

    // getByText lève si l'élément est absent : contrairement au smoke test existant
    // (renderToStaticMarkup + toContain sur une chaîne), ceci passe par le DOM réel que
    // React 19 construit, avec act() correctement configuré.
    expect(screen.getByText(/Hikari/i)).toBeInTheDocument();
  });
});
