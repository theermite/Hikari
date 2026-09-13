// Tests écrits APRÈS un défaut trouvé par relecture indépendante (2026-09-13) : la
// bannière de "Démarrer" (`LiveBar.tsx`) et l'écran Paramètres (`EncodingSettingsPanel.tsx`)
// peuvent tous deux écrire ce même fichier pendant que l'autre reste ouvert — `LiveBar` est
// montée sur TOUS les écrans (`Cockpit.tsx`). Écrire l'objet entier depuis un état chargé
// une fois au montage effaçait silencieusement ce que l'autre écran venait de poser.

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

describe("patchEncodingSettings", () => {
  beforeEach(() => {
    storeState.value = null;
    storeMock.get.mockClear();
    storeMock.set.mockClear();
  });

  it("should_keep_a_field_another_screen_just_wrote_while_this_one_only_touches_another", async () => {
    const { patchEncodingSettings } = await import("./encodingSettings");

    // La bannière de "Démarrer" applique un réglage pendant que l'écran Paramètres est
    // resté ouvert, avec son propre état chargé plus tôt.
    await patchEncodingSettings({ composition: "1280x720@60" });
    // L'écran Paramètres touche un AUTRE champ, sans savoir que `composition` a changé.
    const result = await patchEncodingSettings({ encoder: "nvenc" });

    expect(result.composition).toBe("1280x720@60");
    expect(result.encoder).toBe("nvenc");
  });

  it("should_start_from_the_saved_defaults_when_nothing_was_ever_written", async () => {
    const { patchEncodingSettings } = await import("./encodingSettings");

    const result = await patchEncodingSettings({ bitrateKbps: "4000" });

    expect(result).toEqual({
      composition: "auto",
      encoder: "auto",
      bitrateKbps: "4000",
    });
  });
});
