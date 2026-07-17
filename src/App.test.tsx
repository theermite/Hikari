import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import App from "./App";

// Test smoke du socle : rendu sans jsdom ni `act` (React 19.2 / RTL incompatibles pour
// l'instant). Le test interactif (jsdom + Testing Library) sera câblé en B1, veille fraîche.
describe("App shell", () => {
  it("should_render_shell_when_mounted", () => {
    const html = renderToStaticMarkup(<App />);
    expect(html).toContain("Hikari");
  });
});
