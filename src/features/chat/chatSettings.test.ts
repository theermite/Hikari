import { beforeEach, describe, expect, it, vi } from "vitest";

const storeState = vi.hoisted(() => ({ value: null as unknown }));

const storeMock = vi.hoisted(() => ({
  get: vi.fn(async () => storeState.value),
  set: vi.fn(async (_key: string, value: unknown) => {
    storeState.value = value;
  }),
}));

vi.mock("@tauri-apps/plugin-store", () => ({
  load: vi.fn(async () => storeMock),
}));

describe("chat settings", () => {
  beforeEach(() => {
    storeState.value = null;
    storeMock.get.mockClear();
    storeMock.set.mockClear();
  });

  it("should_start_from_the_default_when_nothing_was_ever_saved", async () => {
    const { loadChatSettings } = await import("./chatSettings");

    const settings = await loadChatSettings();

    expect(settings).toEqual({ showTimestamps: false, alertMedia: {} });
  });

  it("should_roundtrip_a_saved_preference", async () => {
    const { loadChatSettings, saveChatSettings } = await import(
      "./chatSettings"
    );

    await saveChatSettings({ showTimestamps: true, alertMedia: {} });
    const settings = await loadChatSettings();

    expect(settings).toEqual({ showTimestamps: true, alertMedia: {} });
  });

  it("should_merge_a_patch_onto_the_store_read_at_patch_time_not_a_stale_caller_state", async () => {
    // Deux écrans écrivent ce fichier : l'écran Chat (bouton horloge) et l'écran de
    // réglage des alertes. Un `set` complet reconstruit depuis un état chargé au montage
    // effacerait ce que l'autre vient de poser — même défaut vécu sur l'encodage.
    const { loadChatSettings, saveChatSettings, patchChatSettings } = await import(
      "./chatSettings"
    );

    await saveChatSettings({
      showTimestamps: false,
      alertMedia: {
        follow: { scene: "main", kind: "image", path: "C:\\a.png", durationMs: 2_000 },
      },
    });
    // Un autre écran patch un champ SANS connaître le reste.
    const result = await patchChatSettings({ showTimestamps: true });

    expect(result.showTimestamps).toBe(true);
    expect(result.alertMedia.follow).toEqual({
      scene: "main",
      kind: "image",
      path: "C:\\a.png",
      durationMs: 2_000,
    });
    expect(await loadChatSettings()).toEqual(result);
  });

  it("should_roundtrip_an_alert_media_rule", async () => {
    // Un média pop-up (F-033/F-034) déclenché par une alerte : le moteur veut le kind
    // et le chemin exacts, aucune déduction depuis l'extension (ambiguë sur .gif).
    const { loadChatSettings, saveChatSettings } = await import(
      "./chatSettings"
    );

    await saveChatSettings({
      showTimestamps: false,
      alertMedia: {
        cheer: { scene: "main", kind: "video", path: "C:\\hype.mp4", durationMs: 4_000 },
      },
    });
    const settings = await loadChatSettings();

    expect(settings.alertMedia.cheer).toEqual({
      scene: "main",
      kind: "video",
      path: "C:\\hype.mp4",
      durationMs: 4_000,
    });
  });
});
