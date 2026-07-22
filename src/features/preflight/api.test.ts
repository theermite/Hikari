import { beforeEach, describe, expect, it, vi } from "vitest";

// Same constraint as `deck/api.test.ts`: no Tauri runtime under vitest — `invoke` is
// mocked so only the WIRING (command name, response shape) is under test.
vi.mock("@tauri-apps/api/core", () => ({
  invoke: vi.fn(),
}));

import { invoke } from "@tauri-apps/api/core";
import { runPreflight } from "./api";

describe("preflight api", () => {
  beforeEach(() => {
    vi.mocked(invoke).mockReset();
  });

  it("should_call_run_preflight_command_when_checking", async () => {
    vi.mocked(invoke).mockResolvedValueOnce({
      ok: true,
      encoder_name: "OBS_NVENC_H264_TEX",
      hardware: true,
      reason: null,
    });

    const outcome = await runPreflight();

    expect(invoke).toHaveBeenCalledExactlyOnceWith("run_preflight");
    expect(outcome).toEqual({
      ok: true,
      encoder_name: "OBS_NVENC_H264_TEX",
      hardware: true,
      reason: null,
    });
  });

  it("should_return_blocked_outcome_when_no_encoder_detected", async () => {
    vi.mocked(invoke).mockResolvedValueOnce({
      ok: false,
      encoder_name: null,
      hardware: null,
      reason: "aucun encodeur reconnu détecté",
    });

    const outcome = await runPreflight();

    expect(outcome.ok).toBe(false);
    expect(outcome.reason).toBe("aucun encodeur reconnu détecté");
  });
});
