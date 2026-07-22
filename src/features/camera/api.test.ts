import { beforeEach, describe, expect, it, vi } from "vitest";

// Same constraint as `preflight/api.test.ts`: no Tauri runtime under vitest — `invoke` is
// mocked so only the WIRING (command name, response shape) is under test.
vi.mock("@tauri-apps/api/core", () => ({
  invoke: vi.fn(),
}));

import { invoke } from "@tauri-apps/api/core";
import { listCameras } from "./api";

describe("camera api", () => {
  beforeEach(() => {
    vi.mocked(invoke).mockReset();
  });

  it("should_call_list_cameras_command_when_listing", async () => {
    vi.mocked(invoke).mockResolvedValueOnce([
      { name: "Webcam HD", device_id: "Webcam HD:usb#vid_0000" },
    ]);

    const devices = await listCameras();

    expect(invoke).toHaveBeenCalledExactlyOnceWith("list_cameras");
    expect(devices).toEqual([
      { name: "Webcam HD", device_id: "Webcam HD:usb#vid_0000" },
    ]);
  });

  it("should_return_empty_list_when_no_camera_detected", async () => {
    vi.mocked(invoke).mockResolvedValueOnce([]);

    const devices = await listCameras();

    expect(devices).toEqual([]);
  });
});
