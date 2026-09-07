// @vitest-environment jsdom
//
// Le contenu d'une fenêtre de réglages séparée (Jay, 2026-09-07 : « une fenêtre qui
// apparaît pour que l'on puisse régler », comme dans OBS). Deux comportements migrés
// depuis ScenesPanel.test.tsx, où ils vivaient tant que les réglages étaient repliés sous
// la ligne de la source : appliquer un filtre caméra, relancer une caméra figée sans la
// retirer (Jay, 2026-09-07, en plein direct).

import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { readSettingsWindowParams, SettingsWindow } from "./SettingsWindow";

const invokeMock = vi.hoisted(() => vi.fn().mockResolvedValue(undefined));
vi.mock("@tauri-apps/api/core", () => ({ invoke: invokeMock }));

let engineListener: ((event: { payload: unknown }) => void) | null = null;
const listenMock = vi.hoisted(() => vi.fn());
vi.mock("@tauri-apps/api/event", () => ({
  listen: listenMock,
  emit: vi.fn().mockResolvedValue(undefined),
}));

function emit(payload: unknown) {
  engineListener?.({ payload });
}

beforeEach(() => {
  invokeMock.mockClear();
  engineListener = null;
  listenMock.mockReset();
  listenMock.mockImplementation(
    (_name: string, handler: typeof engineListener) => {
      engineListener = handler;
      return Promise.resolve(() => {});
    },
  );
});

afterEach(cleanup);

describe("readSettingsWindowParams", () => {
  it("should_read_nothing_from_an_ordinary_url", () => {
    expect(readSettingsWindowParams("")).toBeNull();
  });

  it("should_read_a_camera_settings_url", () => {
    const params = readSettingsWindowParams(
      "?settings=1&kind=camera&scene=main&name=Krom%20Kam",
    );
    expect(params).toEqual({
      kind: "camera",
      scene: "main",
      name: "Krom Kam",
      initial: null,
    });
  });

  it("should_fall_back_cleanly_on_unreadable_initial_json", () => {
    // Un JSON corrompu ne doit jamais casser l'ouverture de la fenêtre.
    const params = readSettingsWindowParams(
      "?settings=1&kind=text&scene=main&name=Titre&initial=%7Bpas-du-json",
    );
    expect(params?.initial).toBeNull();
  });
});

describe("SettingsWindow — caméra", () => {
  it("should_apply_a_filter_to_this_camera_in_this_scene", async () => {
    // Les filtres appartiennent à la caméra ET à la scène : deux caméras d'une même scène
    // peuvent avoir deux allures, et la même caméra deux allures selon la scène.
    const user = userEvent.setup();
    render(
      <SettingsWindow
        kind="camera"
        scene="main"
        name="Logitech StreamCam"
        initial={null}
      />,
    );

    emit({
      type: "scene_list",
      active: "main",
      scenes: [
        {
          name: "main",
          sources: [
            {
              name: "Logitech StreamCam",
              target_id: "cam-1",
              background_removal: false,
              circle_mask: false,
            },
          ],
        },
      ],
    });

    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: /fond IA/i }),
      ).toBeInTheDocument(),
    );
    await user.click(screen.getByRole("button", { name: /fond IA/i }));

    expect(invokeMock).toHaveBeenCalledWith("set_background_removal", {
      deviceId: "cam-1",
      scene: "main",
      enabled: true,
    });
  });

  it("should_restart_a_frozen_camera_without_removing_it", async () => {
    // Vécu par Jay le 2026-09-07, en plein direct : sa caméra a figé, et le seul recours
    // était de la retirer puis de la remettre — donc de refaire son cadrage et ses
    // filtres devant les spectateurs.
    const user = userEvent.setup();
    render(
      <SettingsWindow
        kind="camera"
        scene="main"
        name="Krom Kam"
        initial={null}
      />,
    );

    emit({
      type: "scene_list",
      active: "main",
      scenes: [
        {
          name: "main",
          sources: [
            {
              name: "Krom Kam",
              target_id: "cam-1",
              background_removal: false,
              circle_mask: false,
            },
          ],
        },
      ],
    });

    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: /Relancer la caméra/ }),
      ).toBeInTheDocument(),
    );
    await user.click(
      screen.getByRole("button", { name: /Relancer la caméra/ }),
    );

    expect(invokeMock).toHaveBeenCalledWith("restart_camera", {
      deviceId: "cam-1",
    });
    // Rien ne doit la retirer au passage : c'est tout l'intérêt du geste.
    expect(invokeMock).not.toHaveBeenCalledWith(
      "remove_camera_source",
      expect.anything(),
    );
  });
});
