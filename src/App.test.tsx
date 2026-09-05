import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import App from "./App";

// Le cockpit monte `LiveBar`, qui ecoute le moteur des son affichage. Sans bouchon, cette
// ecoute part vers un pont Tauri absent sous jsdom : la promesse ne se resout jamais, la
// boucle d'evenements reste vivante, et la suite COMPLETE ne rend plus la main (mesure du
// 2026-09-04 : delai de 200 s depasse). Un test de coque n'a besoin d'aucun vrai moteur.
vi.mock("@tauri-apps/api/event", () => ({
  listen: () => Promise.resolve(() => {}),
}));
vi.mock("@tauri-apps/api/core", () => ({ invoke: () => Promise.resolve() }));

// Test smoke du socle : rendu sans jsdom ni `act` (React 19.2 / RTL incompatibles pour
// l'instant). Le test interactif (jsdom + Testing Library) sera câblé en B1, veille fraîche.
describe("App shell", () => {
  it("should_render_shell_when_mounted", () => {
    const html = renderToStaticMarkup(<App />);
    expect(html).toContain("Hikari");
  });
});
