import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@tauri-apps/api/core", () => ({
  invoke: vi.fn(),
}));

import { invoke } from "@tauri-apps/api/core";
import { createScene, switchScene } from "./api";

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
});
