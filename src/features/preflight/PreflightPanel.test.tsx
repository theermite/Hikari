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

const loadMock = vi.hoisted(() => vi.fn());
const saveMock = vi.hoisted(() => vi.fn());
vi.mock("../settings/encodingSettings", async () => {
  const actual = await vi.importActual<
    typeof import("../settings/encodingSettings")
  >("../settings/encodingSettings");
  return {
    ...actual,
    loadEncodingSettings: loadMock,
    saveEncodingSettings: saveMock,
  };
});

const panelProps = {} as IDockviewPanelProps;

beforeEach(() => {
  invokeMock.mockReset();
  loadMock.mockReset();
  saveMock.mockReset();
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
    // Un débit manuel déjà posé (l'écran né du direct à 65 % d'images perdues) — c'est
    // exactement le cas que le défaut laissait intact.
    loadMock.mockResolvedValue({
      composition: "auto",
      encoder: "auto",
      bitrateKbps: "8000",
    });

    render(<PreflightPanel {...panelProps} />);
    fireEvent.click(screen.getByText("Lancer la vérification"));
    await waitFor(() => screen.getByText("Appliquer"));
    fireEvent.click(screen.getByText("Appliquer"));

    await waitFor(() => expect(saveMock).toHaveBeenCalled());
    expect(saveMock).toHaveBeenCalledWith(
      expect.objectContaining({
        composition: "854x480@30",
        bitrateKbps: "auto",
      }),
    );
  });
});
