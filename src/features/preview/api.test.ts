import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@tauri-apps/api/core", () => ({
  invoke: vi.fn(),
}));

import { invoke } from "@tauri-apps/api/core";
import { startEngine, stopEngine } from "./api";

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
});
