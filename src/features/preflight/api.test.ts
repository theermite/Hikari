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
      measured_upload_kbps: 6200,
    });

    const outcome = await runPreflight();

    expect(invoke).toHaveBeenCalledExactlyOnceWith("run_preflight");
    expect(outcome).toEqual({
      ok: true,
      encoder_name: "OBS_NVENC_H264_TEX",
      hardware: true,
      reason: null,
      measured_upload_kbps: 6200,
    });
  });

  it("should_return_blocked_outcome_when_no_encoder_detected", async () => {
    vi.mocked(invoke).mockResolvedValueOnce({
      ok: false,
      encoder_name: null,
      hardware: null,
      reason: "aucun encodeur reconnu détecté",
      measured_upload_kbps: null,
    });

    const outcome = await runPreflight();

    expect(outcome.ok).toBe(false);
    expect(outcome.reason).toBe("aucun encodeur reconnu détecté");
  });

  it("should_return_blocked_outcome_when_the_connection_cannot_sustain_the_bitrate", async () => {
    vi.mocked(invoke).mockResolvedValueOnce({
      ok: false,
      encoder_name: "OBS_X264",
      hardware: false,
      reason:
        "connexion insuffisante : 3000 kbit/s mesurés, 6000 kbit/s nécessaires",
      measured_upload_kbps: 3000,
    });

    const outcome = await runPreflight();

    expect(outcome.ok).toBe(false);
    expect(outcome.measured_upload_kbps).toBe(3000);
    expect(outcome.reason).toContain("connexion insuffisante");
  });
});
