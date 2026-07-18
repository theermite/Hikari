import { beforeEach, describe, expect, it, vi } from "vitest";

// Same constraint as `layout.test.ts`: no Tauri runtime under vitest — `invoke` is
// mocked so only the WIRING (command name, payload shape) is under test, never a real IPC.
vi.mock("@tauri-apps/api/core", () => ({
  invoke: vi.fn(),
}));

import { invoke } from "@tauri-apps/api/core";
import { listDeckKeys, triggerDeckKey } from "./api";

describe("deck api", () => {
  beforeEach(() => {
    vi.mocked(invoke).mockReset();
  });

  it("should_call_deck_list_keys_command_when_listing", async () => {
    vi.mocked(invoke).mockResolvedValueOnce([
      { id: "marker", label: "Marqueur" },
    ]);

    const keys = await listDeckKeys();

    expect(invoke).toHaveBeenCalledExactlyOnceWith("deck_list_keys");
    expect(keys).toEqual([{ id: "marker", label: "Marqueur" }]);
  });

  it("should_call_deck_trigger_key_command_with_id_when_triggering", async () => {
    vi.mocked(invoke).mockResolvedValueOnce({ status: "dispatched" });

    const outcome = await triggerDeckKey("marker");

    expect(invoke).toHaveBeenCalledExactlyOnceWith("deck_trigger_key", {
      id: "marker",
    });
    expect(outcome).toEqual({ status: "dispatched" });
  });
});
