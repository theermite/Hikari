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

  it("should_default_alert_media_when_reading_a_file_saved_before_that_field_existed", async () => {
    // Vécu en vrai le 2026-09-15 : le fichier réel de Jay ne portait que showTimestamps
    // (écrit par la 0.6.0, avant alertMedia) — le lire tel quel plantait l'écran de
    // réglage sur `undefined[kind]`, page blanche silencieuse.
    storeState.value = { showTimestamps: true };

    const { loadChatSettings } = await import("./chatSettings");
    const settings = await loadChatSettings();

    expect(settings).toEqual({ showTimestamps: true, alertMedia: {} });
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
        follow: { durationMs: 2_000 },
      },
    });
    // Un autre écran patch un champ SANS connaître le reste.
    const result = await patchChatSettings({ showTimestamps: true });

    expect(result.showTimestamps).toBe(true);
    expect(result.alertMedia.follow).toEqual({ durationMs: 2_000 });
    expect(await loadChatSettings()).toEqual(result);
  });

  it("should_roundtrip_an_alert_media_rule", async () => {
    // Un média pop-up (F-033/F-034) déclenché par une alerte : la source vit en
    // permanence dans la médiathèque, sous le nom du type d'alerte — seule la durée
    // d'affichage est un réglage propre à ce type.
    const { loadChatSettings, saveChatSettings } = await import(
      "./chatSettings"
    );

    await saveChatSettings({
      showTimestamps: false,
      alertMedia: {
        cheer: { durationMs: 4_000 },
      },
    });
    const settings = await loadChatSettings();

    expect(settings.alertMedia.cheer).toEqual({ durationMs: 4_000 });
  });
});
