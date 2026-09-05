// Le « + » d'un onglet doit atteindre son panneau, et ne rien casser quand il n'y a
// personne pour l'entendre.

import { describe, expect, it, vi } from "vitest";
import { acceptsAdd, onAddRequested, requestAdd } from "./panelActions";

describe("panelActions", () => {
  it("should_reach_the_panel_that_registered", () => {
    const handler = vi.fn();
    const off = onAddRequested("scenes", handler);

    requestAdd("scenes");

    expect(handler).toHaveBeenCalledTimes(1);
    off();
  });

  it("should_do_nothing_when_nobody_listens", () => {
    // Un panneau ferme ne doit pas faire echouer un clic sur son onglet.
    expect(() => requestAdd("panneau-absent")).not.toThrow();
  });

  it("should_never_reach_another_panel", () => {
    const scenes = vi.fn();
    const audio = vi.fn();
    const offScenes = onAddRequested("scenes", scenes);
    const offAudio = onAddRequested("audio", audio);

    requestAdd("audio");

    expect(audio).toHaveBeenCalledTimes(1);
    expect(scenes).not.toHaveBeenCalled();
    offScenes();
    offAudio();
  });

  it("should_stop_reaching_a_panel_that_unsubscribed", () => {
    // Un panneau demonte laisserait sinon un ecouteur vivant sur un composant disparu.
    const handler = vi.fn();
    const off = onAddRequested("scenes", handler);
    off();

    requestAdd("scenes");

    expect(handler).not.toHaveBeenCalled();
  });

  it("should_report_whether_a_panel_accepts_an_add", () => {
    // Sert a ne dessiner le « + » que la ou il agit — jamais un bouton mort.
    expect(acceptsAdd("scenes")).toBe(false);
    const off = onAddRequested("scenes", () => {});
    expect(acceptsAdd("scenes")).toBe(true);
    off();
    expect(acceptsAdd("scenes")).toBe(false);
  });
});
