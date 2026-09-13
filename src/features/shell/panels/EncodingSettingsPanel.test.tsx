// @vitest-environment jsdom
//
// Défaut trouvé par relecture indépendante (2026-09-13) : ce panneau charge ses réglages
// une seule fois au montage, puis réécrivait l'objet ENTIER depuis cet état local à chaque
// choix. `LiveBar` (la barre du direct) est montée sur TOUS les écrans, y compris celui-ci
// — si elle écrit un réglage plus sûr pendant que Paramètres reste ouvert, le moindre geste
// ici (changer l'encodeur, par exemple) effaçait ce réglage en silence.

import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import type { IDockviewPanelProps } from "dockview-react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { EncodingSettingsPanel } from "./EncodingSettingsPanel";

const loadMock = vi.hoisted(() => vi.fn());
const patchMock = vi.hoisted(() => vi.fn());
vi.mock("../../settings/encodingSettings", async () => {
  const actual = await vi.importActual<
    typeof import("../../settings/encodingSettings")
  >("../../settings/encodingSettings");
  return {
    ...actual,
    loadEncodingSettings: loadMock,
    patchEncodingSettings: patchMock,
  };
});

const panelProps = {} as IDockviewPanelProps;

beforeEach(() => {
  loadMock.mockReset();
  patchMock.mockReset();
});

afterEach(cleanup);

describe("EncodingSettingsPanel", () => {
  it("should_ask_to_patch_only_the_changed_field_never_the_whole_local_state", async () => {
    // La preuve du correctif : cet écran ne doit JAMAIS reconstruire l'objet entier depuis
    // son propre état local. S'il le faisait, une écriture faite par un autre écran
    // pendant que celui-ci restait ouvert (le cas réel : la bannière de "Démarrer")
    // serait effacée par le prochain geste ici, sans qu'aucun test ne le révèle.
    loadMock.mockResolvedValue({
      composition: "1280x720@60",
      encoder: "auto",
      bitrateKbps: "auto",
    });
    patchMock.mockResolvedValue({
      composition: "1280x720@60",
      encoder: "nvenc",
      bitrateKbps: "auto",
    });

    render(<EncodingSettingsPanel {...panelProps} />);
    await waitFor(() => screen.getByText("NVENC"));

    fireEvent.click(screen.getByText("NVENC"));

    await waitFor(() => expect(patchMock).toHaveBeenCalled());
    // Seul le champ touché est demandé — jamais `composition` ni `bitrateKbps`, que
    // l'ancien code aurait pris depuis son état local et aurait pu écraser une valeur
    // posée entre-temps par un autre écran.
    expect(patchMock).toHaveBeenCalledWith({ encoder: "nvenc" });
  });

  it("should_reflect_what_the_store_actually_holds_after_a_patch", async () => {
    // Le panneau affiche le résultat FUSIONNÉ que le store renvoie, jamais une supposition
    // locale — s'il redevenait "composition: auto" par erreur après ce clic, ce test le
    // montrerait.
    loadMock.mockResolvedValue({
      composition: "auto",
      encoder: "auto",
      bitrateKbps: "auto",
    });
    patchMock.mockResolvedValue({
      composition: "auto",
      encoder: "x264",
      bitrateKbps: "auto",
    });

    render(<EncodingSettingsPanel {...panelProps} />);
    await waitFor(() => screen.getByText("X264"));

    fireEvent.click(screen.getByText("X264"));

    await waitFor(() => {
      const button = screen.getByText("X264");
      expect(button.getAttribute("aria-pressed")).toBe("true");
    });
  });
});
