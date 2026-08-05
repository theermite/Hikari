import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@tauri-apps/api/core", () => ({
  invoke: vi.fn(),
}));

import { invoke } from "@tauri-apps/api/core";
import {
  addCaptureSource,
  createScene,
  deleteScene,
  listCaptureTargets,
  removeSource,
  switchScene,
} from "./api";

describe("scenes api", () => {
  beforeEach(() => {
    vi.mocked(invoke).mockReset();
  });

  it("should_call_create_scene_command_with_name_when_creating", async () => {
    vi.mocked(invoke).mockResolvedValueOnce(undefined);

    await createScene("Jeu");

    expect(invoke).toHaveBeenCalledExactlyOnceWith("create_scene", {
      name: "Jeu",
    });
  });

  it("should_call_switch_scene_command_with_name_when_switching", async () => {
    vi.mocked(invoke).mockResolvedValueOnce(undefined);

    await switchScene("Discussion");

    expect(invoke).toHaveBeenCalledExactlyOnceWith("switch_scene", {
      name: "Discussion",
    });
  });

  it("should_call_delete_scene_command_with_name_when_deleting", async () => {
    vi.mocked(invoke).mockResolvedValueOnce(undefined);

    await deleteScene("Jeu");

    expect(invoke).toHaveBeenCalledExactlyOnceWith("delete_scene", {
      name: "Jeu",
    });
  });

  it("should_call_list_capture_targets_command_when_listing", async () => {
    vi.mocked(invoke).mockResolvedValueOnce(undefined);

    await listCaptureTargets();

    expect(invoke).toHaveBeenCalledExactlyOnceWith("list_capture_targets");
  });

  it("should_pass_scene_kind_target_and_name_when_adding_a_capture", async () => {
    vi.mocked(invoke).mockResolvedValueOnce(undefined);

    await addCaptureSource("main", "game", "LoL", "Jeu");

    expect(invoke).toHaveBeenCalledExactlyOnceWith("add_capture_source", {
      scene: "main",
      kind: "game",
      targetId: "LoL",
      name: "Jeu",
    });
  });

  it("should_pass_the_scene_when_removing_a_source", async () => {
    // La source part d'UNE scène, pas de toutes : le nom seul ne suffirait pas.
    vi.mocked(invoke).mockResolvedValueOnce(undefined);

    await removeSource("main", "Jeu");

    expect(invoke).toHaveBeenCalledExactlyOnceWith("remove_source", {
      scene: "main",
      name: "Jeu",
    });
  });
});
