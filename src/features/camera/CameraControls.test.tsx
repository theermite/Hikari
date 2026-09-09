// @vitest-environment jsdom
//
// Le sélecteur de forme de masque (B-filtres, 2026-09-09) — Aucun / Cercle / Coins arrondis,
// une seule forme active à la fois. Écrit après le composant cette fois (session en cours
// avec Jay), mais vérifié avant de le déclarer fait.

import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { CameraControls, type PlacedCamera } from "./CameraControls";

const invokeMock = vi.hoisted(() => vi.fn().mockResolvedValue(undefined));
vi.mock("@tauri-apps/api/core", () => ({ invoke: invokeMock }));

function camera(over: Partial<PlacedCamera> = {}): PlacedCamera {
  return {
    deviceId: "cam-1",
    name: "Webcam",
    backgroundRemoval: false,
    maskShape: { kind: "none" },
    ...over,
  };
}

function poser(c: PlacedCamera = camera()) {
  render(<CameraControls camera={c} scene="main" />);
}

/** Le dernier appel au moteur pour CETTE commande. */
function lastCallTo(command: string) {
  const calls = invokeMock.mock.calls.filter(([name]) => name === command);
  return calls[calls.length - 1]?.[1];
}

beforeEach(() => {
  invokeMock.mockClear();
});

afterEach(cleanup);

describe("CameraControls — forme de masque", () => {
  it("should_show_the_three_shapes_with_none_pressed_by_default", () => {
    poser();

    expect(screen.getByRole("button", { name: "Aucun" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(screen.getByRole("button", { name: "Cercle" })).toHaveAttribute(
      "aria-pressed",
      "false",
    );
    expect(
      screen.getByRole("button", { name: "Coins arrondis" }),
    ).toHaveAttribute("aria-pressed", "false");
  });

  it("should_send_circle_to_the_engine_when_chosen", async () => {
    const user = userEvent.setup();
    poser();

    await user.click(screen.getByRole("button", { name: "Cercle" }));

    expect(lastCallTo("set_mask_shape")).toEqual({
      deviceId: "cam-1",
      scene: "main",
      shape: { kind: "circle" },
    });
  });

  it("should_send_none_to_the_engine_when_switching_back_off", async () => {
    const user = userEvent.setup();
    poser(camera({ maskShape: { kind: "circle" } }));

    await user.click(screen.getByRole("button", { name: "Aucun" }));

    expect(lastCallTo("set_mask_shape")).toEqual({
      deviceId: "cam-1",
      scene: "main",
      shape: { kind: "none" },
    });
  });

  it("should_show_no_radius_slider_unless_rounded_is_active", () => {
    poser(camera({ maskShape: { kind: "circle" } }));

    expect(
      screen.queryByLabelText(/rayon des coins arrondis/i),
    ).not.toBeInTheDocument();
  });

  it("should_send_a_default_radius_when_choosing_rounded", async () => {
    const user = userEvent.setup();
    poser();

    await user.click(screen.getByRole("button", { name: "Coins arrondis" }));

    expect(lastCallTo("set_mask_shape")).toEqual({
      deviceId: "cam-1",
      scene: "main",
      shape: { kind: "rounded", radius_percent: 20 },
    });
  });

  it("should_show_the_radius_slider_once_rounded_is_active", () => {
    poser(camera({ maskShape: { kind: "rounded", radius_percent: 30 } }));

    const slider = screen.getByLabelText(/rayon des coins arrondis/i);
    expect(slider).toHaveValue("30");
  });

  it("should_show_the_dragged_value_without_calling_the_engine_yet", () => {
    // Le retour visuel suit chaque pas ; l'envoi au moteur, lui, attend le relâchement —
    // sinon un seul glissement de bout en bout produit jusqu'à 51 appels moteur en série
    // (relecture indépendante avant publication, 2026-09-09 : jusqu'à 1,7 s de blocage
    // cumulé sur le fil unique du moteur pour un seul geste).
    poser(camera({ maskShape: { kind: "rounded", radius_percent: 30 } }));

    fireEvent.change(screen.getByLabelText(/rayon des coins arrondis/i), {
      target: { value: "45" },
    });

    expect(screen.getByLabelText(/rayon des coins arrondis/i)).toHaveValue(
      "45",
    );
    expect(lastCallTo("set_mask_shape")).toBeUndefined();
  });

  it("should_send_the_new_radius_only_once_released", () => {
    poser(camera({ maskShape: { kind: "rounded", radius_percent: 30 } }));
    const slider = screen.getByLabelText(/rayon des coins arrondis/i);

    fireEvent.change(slider, { target: { value: "38" } });
    fireEvent.change(slider, { target: { value: "42" } });
    fireEvent.change(slider, { target: { value: "45" } });
    expect(lastCallTo("set_mask_shape")).toBeUndefined();

    fireEvent.mouseUp(slider);

    // Une seule commande, portant la DERNIÈRE valeur du glissement — jamais une par pas.
    expect(
      invokeMock.mock.calls.filter(([name]) => name === "set_mask_shape"),
    ).toHaveLength(1);
    expect(lastCallTo("set_mask_shape")).toEqual({
      deviceId: "cam-1",
      scene: "main",
      shape: { kind: "rounded", radius_percent: 45 },
    });
  });

  it("should_send_the_radius_after_a_keyboard_adjustment_too", () => {
    // Les flèches clavier changent aussi la valeur d'un `<input type="range">` — même
    // geste de relâchement, via `keyup` plutôt que `mouseup`.
    poser(camera({ maskShape: { kind: "rounded", radius_percent: 30 } }));
    const slider = screen.getByLabelText(/rayon des coins arrondis/i);

    fireEvent.change(slider, { target: { value: "31" } });
    fireEvent.keyUp(slider);

    expect(lastCallTo("set_mask_shape")).toEqual({
      deviceId: "cam-1",
      scene: "main",
      shape: { kind: "rounded", radius_percent: 31 },
    });
  });

  it("should_send_nothing_when_releasing_the_slider_without_any_real_change", () => {
    // Un clic sur le curseur sans le déplacer, ou une tabulation qui lui donne le focus,
    // déclenche mouseup/keyup SANS passer par onChange — la commande ne doit partir que si
    // la valeur diffère réellement de celle déjà connue du moteur (relecture indépendante
    // avant publication, second passage, 2026-09-09 : une ref maintenue à part avait pu
    // dériver de l'affichage et partait quand même dans ce cas).
    poser(camera({ maskShape: { kind: "rounded", radius_percent: 30 } }));
    const slider = screen.getByLabelText(/rayon des coins arrondis/i);

    fireEvent.mouseUp(slider);
    fireEvent.keyUp(slider);

    expect(lastCallTo("set_mask_shape")).toBeUndefined();
  });

  it("should_send_exactly_the_radius_shown_even_after_switching_shape_mid_gesture", async () => {
    // Le défaut trouvé en relecture : une ref séparée du rayon ne se resynchronisait pas
    // quand la forme changeait entre-temps (cercle puis coins arrondis), et pouvait envoyer
    // au moteur une valeur (ici 60, la ref restée de l'état initial) que l'utilisateur
    // n'avait jamais vue affichée — l'écran montre 20 (le défaut), pas 60.
    const user = userEvent.setup();
    poser(camera({ maskShape: { kind: "rounded", radius_percent: 60 } }));

    await user.click(screen.getByRole("button", { name: "Cercle" }));
    await user.click(screen.getByRole("button", { name: "Coins arrondis" }));

    const slider = screen.getByLabelText(/rayon des coins arrondis/i);
    expect(slider).toHaveValue("20");
    fireEvent.keyUp(slider);

    expect(lastCallTo("set_mask_shape")).toEqual({
      deviceId: "cam-1",
      scene: "main",
      shape: { kind: "rounded", radius_percent: 20 },
    });
  });

  it("should_keep_the_current_radius_instead_of_resetting_to_the_default", async () => {
    // Sans cette garde, recliquer « Coins arrondis » alors qu'il est déjà actif ramènerait
    // le rayon au défaut (20) au lieu de garder celui que l'utilisateur a réglé (40).
    const user = userEvent.setup();
    poser(camera({ maskShape: { kind: "rounded", radius_percent: 40 } }));

    await user.click(screen.getByRole("button", { name: "Coins arrondis" }));

    expect(lastCallTo("set_mask_shape")).toEqual({
      deviceId: "cam-1",
      scene: "main",
      shape: { kind: "rounded", radius_percent: 40 },
    });
  });
});
