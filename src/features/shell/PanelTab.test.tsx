// @vitest-environment jsdom
//
// Tests écrits AVANT le code (TDG).
//
// L'en-tête d'une carte, tel que la maquette le dessine : le nom, sa pastille, puis les
// outils de la carte — déplacer le panneau, le détacher sur un autre écran.
//
// Les deux outils sont DESSINÉS et marqués « à venir », jamais cachés. Décision de Jay du
// 2026-09-05 : on dessine le squelette complet, on sait ce qui arrive, et le squelette
// tient au lieu d'être rapiécé. Ici c'est doublement vrai — le glisser-déposer est cassé
// dans ce moteur d'affichage, et le détachement attend son étude. Un bouton absent
// laisserait croire à un oubli ; un bouton marqué renseigne.

import { cleanup, render, screen } from "@testing-library/react";
import type { IDockviewPanelHeaderProps } from "dockview-react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { PanelTab } from "./PanelTab";

vi.mock("@tauri-apps/api/core", () => ({ invoke: vi.fn() }));

function tab(id: string, title: string) {
  return {
    api: { id, title, setActive: vi.fn() },
  } as unknown as IDockviewPanelHeaderProps;
}

afterEach(cleanup);

describe("PanelTab", () => {
  it("should_carry_the_panel_name", () => {
    render(<PanelTab {...tab("scenes", "Scènes")} />);

    expect(screen.getByText("Scènes")).toBeInTheDocument();
  });

  it("should_draw_the_card_tools_the_mockup_promises", () => {
    render(<PanelTab {...tab("scenes", "Scènes")} />);

    expect(screen.getByLabelText(/Déplacer le panneau/)).toBeInTheDocument();
    expect(
      screen.getByLabelText(/Détacher sur un autre écran/),
    ).toBeInTheDocument();
  });

  it("should_mark_the_card_tools_as_not_working_yet", () => {
    // Le glisser-déposer est cassé dans ce moteur d'affichage et le détachement n'est pas
    // construit. Un bouton qui FAIT SEMBLANT de marcher trompe ; marqué, il renseigne.
    render(<PanelTab {...tab("scenes", "Scènes")} />);

    for (const label of [
      /Déplacer le panneau/,
      /Détacher sur un autre écran/,
    ]) {
      expect(
        screen.getByLabelText(label).closest('[aria-disabled="true"]'),
      ).not.toBeNull();
    }
  });

  it("should_keep_the_working_add_button_apart_from_them", () => {
    // Le « + » des scènes marche vraiment : le noyer parmi des outils grisés le rendrait
    // douteux.
    render(<PanelTab {...tab("scenes", "Scènes")} />);
    const ajouter = screen.getByRole("button", { name: /Ajouter une scène/ });

    expect(ajouter.closest('[aria-disabled="true"]')).toBeNull();
  });
});
