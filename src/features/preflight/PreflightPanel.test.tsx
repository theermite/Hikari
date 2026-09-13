// @vitest-environment jsdom
//
// Défaut trouvé par relecture indépendante (2026-09-12), après un premier passage qui avait
// déjà fermé 3 autres défauts sur le même pré-vol : « Appliquer » ne réécrivait que la
// résolution proposée, jamais le débit. Un débit choisi à la main PRIME sur la résolution
// au démarrage du direct (`stream.rs`) — l'appliquer sans y toucher laissait le moteur
// envoyer l'ancien débit malgré l'écran affichant « Appliqué ».

import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import type { IDockviewPanelProps } from "dockview-react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { PreflightPanel } from "./PreflightPanel";

const invokeMock = vi.hoisted(() => vi.fn());
vi.mock("@tauri-apps/api/core", () => ({ invoke: invokeMock }));

// `patchEncodingSettings` (relit le store avant d'écrire, corrigé après relecture
// indépendante 2026-09-13) est déjà testée en propre côté `encodingSettings.test.ts` —
// ici on ne vérifie que l'appel, pas la fusion elle-même.
const patchMock = vi.hoisted(() => vi.fn());
vi.mock("../settings/encodingSettings", async () => {
  const actual = await vi.importActual<
    typeof import("../settings/encodingSettings")
  >("../settings/encodingSettings");
  return {
    ...actual,
    patchEncodingSettings: patchMock,
  };
});

const panelProps = {} as IDockviewPanelProps;

beforeEach(() => {
  invokeMock.mockReset();
  patchMock.mockReset();
  patchMock.mockResolvedValue(undefined);
});

afterEach(cleanup);

describe("PreflightPanel", () => {
  it("should_reset_a_manual_bitrate_to_auto_when_applying_the_proposed_composition", async () => {
    invokeMock.mockResolvedValue({
      ok: true,
      encoder_name: "OBS_NVENC_H264_TEX",
      hardware: true,
      reason: null,
      measured_upload_kbps: 5000,
      proposed_composition: { width: 854, height: 480, fps: 30 },
      proposed_bitrate_kbps: 1500,
    });

    render(<PreflightPanel {...panelProps} />);
    fireEvent.click(screen.getByText("Lancer la vérification"));
    await waitFor(() => screen.getByText("Appliquer"));
    fireEvent.click(screen.getByText("Appliquer"));

    await waitFor(() => expect(patchMock).toHaveBeenCalled());
    expect(patchMock).toHaveBeenCalledWith({
      composition: "854x480@30",
      bitrateKbps: "auto",
    });
  });
});
