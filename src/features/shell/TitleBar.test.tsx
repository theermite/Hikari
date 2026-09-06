// @vitest-environment jsdom
//
// Tests écrits AVANT le composant (TDG).
//
// Demandé par Jay le 2026-09-06 : la barre de Windows en haut de la fenêtre est un
// bandeau étranger au-dessus du cockpit. Les trois boutons rentrent dans l'application,
// et la barre grise disparaît.
//
// Ce que ces tests protègent : les trois gestes existent, ils sont NOMMÉS (un lecteur
// d'écran ne voit pas un pictogramme), et fermer la fenêtre reste distinct de la réduire.

import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { TitleBar } from "./TitleBar";

const minimize = vi.hoisted(() => vi.fn());
const toggleMaximize = vi.hoisted(() => vi.fn());
const close = vi.hoisted(() => vi.fn());

vi.mock("@tauri-apps/api/window", () => ({
  getCurrentWindow: () => ({ minimize, toggleMaximize, close }),
}));

beforeEach(() => {
  minimize.mockReset();
  toggleMaximize.mockReset();
  close.mockReset();
});

afterEach(cleanup);

describe("TitleBar", () => {
  it("should_leave_the_name_to_the_sidebar_that_already_carries_it", () => {
    // La barre latérale affiche le nom et la devise juste en dessous. L'écrire ici aussi
    // le dirait deux fois dans les deux premiers centimètres de la fenêtre.
    render(<TitleBar />);

    expect(screen.queryByText("Hikari")).not.toBeInTheDocument();
  });

  it("should_minimize_the_window_when_asked", async () => {
    const user = userEvent.setup();
    render(<TitleBar />);

    await user.click(screen.getByRole("button", { name: /réduire/i }));

    expect(minimize).toHaveBeenCalledTimes(1);
    expect(close).not.toHaveBeenCalled();
  });

  it("should_toggle_the_full_screen_size_when_asked", async () => {
    const user = userEvent.setup();
    render(<TitleBar />);

    await user.click(screen.getByRole("button", { name: /agrandir/i }));

    expect(toggleMaximize).toHaveBeenCalledTimes(1);
  });

  it("should_close_the_window_when_asked", async () => {
    const user = userEvent.setup();
    render(<TitleBar />);

    await user.click(screen.getByRole("button", { name: /fermer/i }));

    expect(close).toHaveBeenCalledTimes(1);
  });

  it("should_offer_a_zone_to_drag_the_window_by", () => {
    // Sans elle, une fenêtre sans bordure système n'est plus déplaçable du tout : le
    // geste que la barre grise portait doit être rendu par quelque chose.
    render(<TitleBar />);

    expect(document.querySelector("[data-tauri-drag-region]")).not.toBeNull();
  });

  it("should_keep_the_buttons_out_of_the_drag_zone", () => {
    // Un bouton posé DANS la zone de déplacement se fait voler son clic par le geste de
    // déplacement : la fenêtre bouge, le bouton ne répond pas.
    render(<TitleBar />);

    const fermer = screen.getByRole("button", { name: /fermer/i });

    expect(fermer.closest("[data-tauri-drag-region]")).toBeNull();
  });
});
