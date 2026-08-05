import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@tauri-apps/api/core", () => ({
  invoke: vi.fn(),
}));

import { invoke } from "@tauri-apps/api/core";
import {
  addAudioSource,
  listAudioDevices,
  removeAudioSource,
  setAudioMonitoring,
  setAudioMuted,
  setAudioVolume,
  setMonitorVolume,
  setNoiseSettings,
} from "./api";

describe("audio api", () => {
  beforeEach(() => {
    vi.mocked(invoke).mockReset();
    vi.mocked(invoke).mockResolvedValue(undefined);
  });

  it("should_call_list_audio_devices_command_when_listing", async () => {
    await listAudioDevices();

    expect(invoke).toHaveBeenCalledExactlyOnceWith("list_audio_devices");
  });

  it("should_pass_the_device_id_kind_and_name_when_adding_a_source", async () => {
    await addAudioSource("{0.0.1}", "input", "Micro");

    expect(invoke).toHaveBeenCalledExactlyOnceWith("add_audio_source", {
      deviceId: "{0.0.1}",
      kind: "input",
      name: "Micro",
    });
  });

  it("should_call_remove_audio_source_command_with_name_when_removing", async () => {
    await removeAudioSource("Micro");

    expect(invoke).toHaveBeenCalledExactlyOnceWith("remove_audio_source", {
      name: "Micro",
    });
  });

  it("should_pass_the_slider_percent_when_setting_volume", async () => {
    await setAudioVolume("Micro", 60);

    expect(invoke).toHaveBeenCalledExactlyOnceWith("set_audio_volume", {
      name: "Micro",
      percent: 60,
    });
  });

  it("should_pass_the_muted_flag_when_muting", async () => {
    await setAudioMuted("Micro", true);

    expect(invoke).toHaveBeenCalledExactlyOnceWith("set_audio_muted", {
      name: "Micro",
      muted: true,
    });
  });

  it("should_pass_the_monitoring_choice_when_routing_playback", async () => {
    await setAudioMonitoring("Micro", "monitor_only");

    expect(invoke).toHaveBeenCalledExactlyOnceWith("set_audio_monitoring", {
      name: "Micro",
      monitoring: "monitor_only",
    });
  });

  it("should_send_the_whole_noise_setting_at_once", async () => {
    // Une combinaison à moitié appliquée (méthode sans réglage + une force) n'a pas de
    // sens : les trois valeurs partent ensemble.
    await setNoiseSettings("Micro", true, "speex", -24);

    expect(invoke).toHaveBeenCalledExactlyOnceWith("set_noise_settings", {
      name: "Micro",
      enabled: true,
      method: "speex",
      levelDb: -24,
    });
  });

  it("should_pass_the_headphone_percent_when_setting_monitor_volume", async () => {
    await setMonitorVolume("Micro", 65);

    expect(invoke).toHaveBeenCalledExactlyOnceWith("set_monitor_volume", {
      name: "Micro",
      percent: 65,
    });
  });
});
