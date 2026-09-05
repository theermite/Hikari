// @vitest-environment jsdom
//
// Le panneau Caméra avec PLUSIEURS caméras (2026-09-06).
//
// Avant, le panneau ne connaissait qu'une caméra posée : un seul bloc de réglages, un seul
// bouton « Retirer ». Poser un deuxième appareil n'avait donc aucun endroit où s'afficher —
// et côté moteur, il renvoyait de toute façon le premier.
//
// Ce que ces tests protègent : chaque caméra de la scène en direct a SES réglages, et un
// geste sur l'une ne parle jamais de l'autre. C'est la seule chose qui rende deux caméras
// utilisables plutôt que seulement possibles.

import { cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { IDockviewPanelProps } from "dockview-react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { CameraPanel } from "./CameraPanel";

const invokeMock = vi.hoisted(() => vi.fn().mockResolvedValue(undefined));
vi.mock("@tauri-apps/api/core", () => ({ invoke: invokeMock }));

let engineListener: ((event: { payload: unknown }) => void) | null = null;
const listenMock = vi.hoisted(() => vi.fn());
vi.mock("@tauri-apps/api/event", () => ({ listen: listenMock }));

const STREAMCAM = "usb#vid_046d&streamcam";
const BRIO = "usb#vid_046d&brio";

/** Une caméra telle que le moteur la décrit dans sa liste de scènes. */
function cameraSource(
  name: string,
  deviceId: string,
  filters: { background?: boolean; circle?: boolean } = {},
) {
  return {
    name,
    kind: "dshow_input",
    source_kind: "camera" as const,
    target_id: deviceId,
    x: 0,
    y: 0,
    scale_percent: 100,
    locked: false,
    background_removal: filters.background ?? false,
    circle_mask: filters.circle ?? false,
  };
}

/** Envoie au panneau la liste de scènes que le moteur émettrait. */
async function engineSays(sources: ReturnType<typeof cameraSource>[]) {
  await vi.waitFor(() => expect(engineListener).not.toBeNull());
  engineListener?.({
    payload: {
      type: "scene_list",
      active: "Jeu",
      scenes: [{ name: "Jeu", has_camera: sources.length > 0, sources }],
    },
  });
}

/** Le bloc de réglages d'une caméra, retrouvé par son nom lisible. */
function controlsFor(name: string) {
  return within(screen.getByRole("region", { name: new RegExp(name, "i") }));
}

describe("CameraPanel", () => {
  beforeEach(() => {
    invokeMock.mockReset();
    invokeMock.mockResolvedValue([
      { name: "Logitech StreamCam", device_id: STREAMCAM },
      { name: "Logitech Brio", device_id: BRIO },
    ]);
    engineListener = null;
    listenMock.mockReset();
    listenMock.mockImplementation((_event: string, handler: never) => {
      engineListener = handler;
      return Promise.resolve(() => {});
    });
  });

  afterEach(cleanup);

  it("should_give_each_camera_of_the_scene_its_own_settings", async () => {
    render(<CameraPanel {...({} as IDockviewPanelProps)} />);

    await engineSays([
      cameraSource("Logitech StreamCam", STREAMCAM),
      cameraSource("Logitech Brio", BRIO),
    ]);

    expect(
      await screen.findByRole("region", { name: /StreamCam/i }),
    ).toBeTruthy();
    expect(screen.getByRole("region", { name: /Brio/i })).toBeTruthy();
  });

  it("should_toggle_the_filter_of_the_camera_the_button_belongs_to", async () => {
    const user = userEvent.setup();
    render(<CameraPanel {...({} as IDockviewPanelProps)} />);

    await engineSays([
      cameraSource("Logitech StreamCam", STREAMCAM),
      cameraSource("Logitech Brio", BRIO),
    ]);
    await screen.findByRole("region", { name: /Brio/i });
    invokeMock.mockReset();
    invokeMock.mockResolvedValue(undefined);

    await user.click(
      controlsFor("Brio").getByRole("button", { name: /fond IA/i }),
    );

    expect(invokeMock).toHaveBeenCalledExactlyOnceWith(
      "set_background_removal",
      {
        deviceId: BRIO,
        scene: "Jeu",
        enabled: true,
      },
    );
  });

  it("should_show_each_camera_its_own_filter_state", async () => {
    render(<CameraPanel {...({} as IDockviewPanelProps)} />);

    await engineSays([
      cameraSource("Logitech StreamCam", STREAMCAM, { background: true }),
      cameraSource("Logitech Brio", BRIO, { background: false }),
    ]);
    await screen.findByRole("region", { name: /Brio/i });

    expect(
      controlsFor("StreamCam").getByRole("button", { name: /fond IA activé/i }),
    ).toBeTruthy();
    expect(
      controlsFor("Brio").getByRole("button", { name: /activer fond IA/i }),
    ).toBeTruthy();
  });

  it("should_remove_only_the_camera_whose_button_was_pressed", async () => {
    const user = userEvent.setup();
    render(<CameraPanel {...({} as IDockviewPanelProps)} />);

    await engineSays([
      cameraSource("Logitech StreamCam", STREAMCAM),
      cameraSource("Logitech Brio", BRIO),
    ]);
    await screen.findByRole("region", { name: /StreamCam/i });
    invokeMock.mockReset();
    invokeMock.mockResolvedValue(undefined);

    await user.click(
      controlsFor("StreamCam").getByRole("button", { name: /retirer/i }),
    );

    expect(invokeMock).toHaveBeenCalledExactlyOnceWith("remove_camera_source", {
      deviceId: STREAMCAM,
      scene: "Jeu",
    });
  });

  it("should_move_only_the_camera_whose_arrow_was_pressed", async () => {
    const user = userEvent.setup();
    render(<CameraPanel {...({} as IDockviewPanelProps)} />);

    await engineSays([
      cameraSource("Logitech StreamCam", STREAMCAM),
      cameraSource("Logitech Brio", BRIO),
    ]);
    await screen.findByRole("region", { name: /Brio/i });
    invokeMock.mockReset();
    invokeMock.mockResolvedValue(undefined);

    await user.click(
      controlsFor("Brio").getByRole("button", { name: /vers la droite/i }),
    );

    expect(invokeMock).toHaveBeenCalledExactlyOnceWith("nudge_camera", {
      deviceId: BRIO,
      scene: "Jeu",
      dx: 40,
      dy: 0,
    });
  });

  /// Une caméra déjà posée ne se repropose pas : cliquer « Ajouter » une seconde fois
  /// n'ouvrirait rien de nouveau, l'appareil étant déjà ouvert.
  it("should_offer_to_add_only_the_devices_the_scene_does_not_show_yet", async () => {
    render(<CameraPanel {...({} as IDockviewPanelProps)} />);

    await engineSays([cameraSource("Logitech StreamCam", STREAMCAM)]);
    await screen.findByRole("region", { name: /StreamCam/i });

    const addButtons = await screen.findAllByRole("button", {
      name: /ajouter à la scène/i,
    });
    expect(addButtons).toHaveLength(1);
  });
});
