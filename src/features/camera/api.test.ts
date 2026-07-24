import { beforeEach, describe, expect, it, vi } from "vitest";

// Same constraint as `preflight/api.test.ts`: no Tauri runtime under vitest — `invoke` is
// mocked so only the WIRING (command name, response shape) is under test.
vi.mock("@tauri-apps/api/core", () => ({
  invoke: vi.fn(),
}));

import { invoke } from "@tauri-apps/api/core";
import {
  addCameraSource,
  listCameras,
  nudgeCamera,
  removeCameraSource,
  scaleCamera,
  setBackgroundRemoval,
  setCircleMask,
} from "./api";

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

  it("should_call_add_camera_source_command_with_device_id_when_adding", async () => {
    vi.mocked(invoke).mockResolvedValueOnce(undefined);

    await addCameraSource("Webcam HD:usb#vid_0000");

    expect(invoke).toHaveBeenCalledExactlyOnceWith("add_camera_source", {
      deviceId: "Webcam HD:usb#vid_0000",
    });
  });

  it("should_call_set_background_removal_command_with_enabled_when_toggling", async () => {
    vi.mocked(invoke).mockResolvedValueOnce(undefined);

    await setBackgroundRemoval(true);

    expect(invoke).toHaveBeenCalledExactlyOnceWith("set_background_removal", {
      enabled: true,
    });
  });

  it("should_call_set_circle_mask_command_with_enabled_when_toggling", async () => {
    vi.mocked(invoke).mockResolvedValueOnce(undefined);

    await setCircleMask(false);

    expect(invoke).toHaveBeenCalledExactlyOnceWith("set_circle_mask", {
      enabled: false,
    });
  });

  it("should_call_remove_camera_source_command_when_removing", async () => {
    vi.mocked(invoke).mockResolvedValueOnce(undefined);

    await removeCameraSource();

    expect(invoke).toHaveBeenCalledExactlyOnceWith("remove_camera_source");
  });

  it("should_call_nudge_camera_command_with_delta_when_moving", async () => {
    vi.mocked(invoke).mockResolvedValueOnce(undefined);

    await nudgeCamera(40, -40);

    expect(invoke).toHaveBeenCalledExactlyOnceWith("nudge_camera", {
      dx: 40,
      dy: -40,
    });
  });

  it("should_call_scale_camera_command_with_grow_when_resizing", async () => {
    vi.mocked(invoke).mockResolvedValueOnce(undefined);

    await scaleCamera(true);

    expect(invoke).toHaveBeenCalledExactlyOnceWith("scale_camera", {
      grow: true,
    });
  });
});
