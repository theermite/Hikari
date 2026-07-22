import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@tauri-apps/api/core", () => ({
  invoke: vi.fn(),
}));

import { invoke } from "@tauri-apps/api/core";
import { hidePreview, positionPreview, startEngine, stopEngine } from "./api";

describe("preview api", () => {
  beforeEach(() => {
    vi.mocked(invoke).mockReset();
  });

  it("should_call_start_engine_command_when_starting", async () => {
    vi.mocked(invoke).mockResolvedValueOnce(undefined);

    await startEngine();

    expect(invoke).toHaveBeenCalledExactlyOnceWith("start_engine");
  });

  it("should_call_stop_engine_command_when_stopping", async () => {
    vi.mocked(invoke).mockResolvedValueOnce(undefined);

    await stopEngine();

    expect(invoke).toHaveBeenCalledExactlyOnceWith("stop_engine");
  });

  it("should_call_position_preview_command_with_rect_when_positioning", async () => {
    vi.mocked(invoke).mockResolvedValueOnce(undefined);

    await positionPreview(10, 20, 300, 150);

    expect(invoke).toHaveBeenCalledExactlyOnceWith("position_preview", {
      x: 10,
      y: 20,
      width: 300,
      height: 150,
    });
  });

  it("should_call_hide_preview_command_when_hiding", async () => {
    vi.mocked(invoke).mockResolvedValueOnce(undefined);

    await hidePreview();

    expect(invoke).toHaveBeenCalledExactlyOnceWith("hide_preview");
  });
});
