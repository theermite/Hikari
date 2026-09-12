// @vitest-environment jsdom
//
// Tests écrits AVANT le composant (TDG).
//
// Ce que cette barre existe pour régler, dit par Jay : « en regardant le cockpit, tu ne
// sais pas si tu diffuses ». Elle ne montre donc QUE ce que le moteur rapporte vraiment —
// pas de compteur de spectateurs tant que les plateformes ne sont pas branchées, jamais un
// zéro trompeur à la place d'une donnée absente.

import { act, cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { formatElapsed, LiveBar } from "./LiveBar";

/** Le pré-vol qui laisse passer — la plupart des tests de cette barre ne parlent QUE du
 * direct lui-même, jamais du pré-vol : ce résultat les laisse traverser sans bannière. */
const PREFLIGHT_OK = {
  ok: true,
  encoder_name: "OBS_NVENC_H264_TEX",
  hardware: true,
  reason: null,
  measured_upload_kbps: 6000,
  proposed_composition: null,
  proposed_bitrate_kbps: null,
};

const invokeMock = vi.hoisted(() => vi.fn());
vi.mock("@tauri-apps/api/core", () => ({ invoke: invokeMock }));

// Déjà testé en détail côté `PreflightPanel.test.tsx` (l'écriture du réglage) — ici on ne
// vérifie que l'ENCHAÎNEMENT (appliquer, puis diffuser), pas l'écriture elle-même.
const applyProposedCompositionMock = vi.hoisted(() => vi.fn());
vi.mock("../preflight/applyProposal", () => ({
  applyProposedComposition: applyProposedCompositionMock,
}));

let listener: ((event: { payload: unknown }) => void) | null = null;
const listenMock = vi.hoisted(() => vi.fn());
vi.mock("@tauri-apps/api/event", () => ({ listen: listenMock }));

function emit(payload: unknown) {
  act(() => {
    listener?.({ payload });
  });
}

beforeEach(() => {
  invokeMock.mockReset();
  invokeMock.mockImplementation((cmd: string) => {
    if (cmd === "run_preflight") return Promise.resolve(PREFLIGHT_OK);
    return Promise.resolve(undefined);
  });
  applyProposedCompositionMock.mockReset();
  applyProposedCompositionMock.mockResolvedValue(undefined);
  listener = null;
  listenMock.mockReset();
  listenMock.mockImplementation((_name: string, handler: typeof listener) => {
    listener = handler;
    return Promise.resolve(() => {});
  });
});

afterEach(cleanup);

describe("LiveBar", () => {
  it("should_offer_to_start_when_nothing_is_streaming", async () => {
    render(<LiveBar />);

    expect(
      await screen.findByRole("button", { name: /démarrer/i }),
    ).toBeTruthy();
    expect(screen.queryByText(/en direct/i)).toBeNull();
  });

  it("should_announce_the_live_state_when_the_engine_reports_it_started", async () => {
    render(<LiveBar />);
    await waitFor(() => expect(listenMock).toHaveBeenCalled());

    emit({ type: "started" });

    expect(screen.getByText(/en direct/i)).toBeTruthy();
    expect(screen.getByRole("button", { name: /arrêter/i })).toBeTruthy();
  });

  it("should_show_a_zeroed_timer_the_moment_it_goes_live", async () => {
    render(<LiveBar />);
    await waitFor(() => expect(listenMock).toHaveBeenCalled());

    emit({ type: "started" });

    expect(screen.getByText("0:00:00")).toBeTruthy();
  });

  it("should_ask_the_engine_to_start_and_wait_for_its_answer", async () => {
    // Le bouton ne bascule PAS l'affichage tout seul : l'état vient du moteur. Basculer
    // à l'optimiste afficherait « en direct » alors que la diffusion a échoué.
    render(<LiveBar />);
    const start = await screen.findByRole("button", { name: /démarrer/i });

    await userEvent.click(start);

    // Le pré-vol tourne D'ABORD (mesure réelle) : l'appel à `start_stream` arrive après,
    // jamais dans le même battement que le clic.
    await waitFor(() =>
      expect(invokeMock).toHaveBeenCalledWith("start_stream"),
    );
    expect(screen.queryByText(/en direct/i)).toBeNull();
  });

  it("should_check_the_connection_before_asking_the_engine_to_start", async () => {
    render(<LiveBar />);
    const start = await screen.findByRole("button", { name: /démarrer/i });

    await userEvent.click(start);

    await waitFor(() =>
      expect(invokeMock).toHaveBeenCalledWith("run_preflight"),
    );
  });

  it("should_show_a_warning_instead_of_starting_when_the_connection_does_not_hold", async () => {
    // Jay, 2026-09-13 : « laisser le choix à l'utilisateur, au moins il était au courant
    // du risque » — jamais un mur, une bannière informée qui laisse la main.
    invokeMock.mockImplementation((cmd: string) => {
      if (cmd === "run_preflight") {
        return Promise.resolve({
          ok: false,
          encoder_name: "OBS_X264",
          hardware: false,
          reason:
            "connexion insuffisante : 3000 kbit/s mesurés, 6000 kbit/s nécessaires",
          measured_upload_kbps: 3000,
          proposed_composition: { width: 1280, height: 720, fps: 60 },
          proposed_bitrate_kbps: 3000,
        });
      }
      return Promise.resolve(undefined);
    });
    render(<LiveBar />);

    await userEvent.click(
      await screen.findByRole("button", { name: /démarrer/i }),
    );

    expect(await screen.findByText(/connexion insuffisante/)).toBeTruthy();
    expect(invokeMock).not.toHaveBeenCalledWith("start_stream");
    expect(screen.queryByText(/en direct/i)).toBeNull();
  });

  it("should_start_anyway_when_the_user_dismisses_the_warning", async () => {
    invokeMock.mockImplementation((cmd: string) => {
      if (cmd === "run_preflight") {
        return Promise.resolve({
          ok: false,
          encoder_name: "OBS_X264",
          hardware: false,
          reason: "connexion insuffisante",
          measured_upload_kbps: 3000,
          proposed_composition: null,
          proposed_bitrate_kbps: null,
        });
      }
      return Promise.resolve(undefined);
    });
    render(<LiveBar />);
    await userEvent.click(
      await screen.findByRole("button", { name: /démarrer/i }),
    );
    await screen.findByText(/diffuser quand même/i);

    await userEvent.click(screen.getByText(/diffuser quand même/i));

    await waitFor(() =>
      expect(invokeMock).toHaveBeenCalledWith("start_stream"),
    );
  });

  it("should_apply_the_suggested_setting_and_start_when_the_user_chooses_it", async () => {
    invokeMock.mockImplementation((cmd: string) => {
      if (cmd === "run_preflight") {
        return Promise.resolve({
          ok: false,
          encoder_name: "OBS_X264",
          hardware: false,
          reason: "connexion insuffisante",
          measured_upload_kbps: 3000,
          proposed_composition: { width: 1280, height: 720, fps: 60 },
          proposed_bitrate_kbps: 3000,
        });
      }
      return Promise.resolve(undefined);
    });
    render(<LiveBar />);
    await userEvent.click(
      await screen.findByRole("button", { name: /démarrer/i }),
    );
    const applyButton = await screen.findByText(/appliquer.*et diffuser/i);

    await userEvent.click(applyButton);

    expect(applyProposedCompositionMock).toHaveBeenCalledWith({
      width: 1280,
      height: 720,
      fps: 60,
    });
    await waitFor(() =>
      expect(invokeMock).toHaveBeenCalledWith("start_stream"),
    );
  });

  it("should_ask_again_without_starting_when_the_user_cancels_the_warning", async () => {
    invokeMock.mockImplementation((cmd: string) => {
      if (cmd === "run_preflight") {
        return Promise.resolve({
          ok: false,
          encoder_name: "OBS_X264",
          hardware: false,
          reason: "connexion insuffisante",
          measured_upload_kbps: 3000,
          proposed_composition: null,
          proposed_bitrate_kbps: null,
        });
      }
      return Promise.resolve(undefined);
    });
    render(<LiveBar />);
    await userEvent.click(
      await screen.findByRole("button", { name: /démarrer/i }),
    );
    await screen.findByText(/diffuser quand même/i);

    await userEvent.click(screen.getByText(/^annuler$/i));

    expect(screen.queryByText(/diffuser quand même/i)).toBeNull();
    expect(invokeMock).not.toHaveBeenCalledWith("start_stream");
  });

  it("should_ask_the_engine_to_stop_when_live", async () => {
    render(<LiveBar />);
    await waitFor(() => expect(listenMock).toHaveBeenCalled());
    emit({ type: "started" });

    await userEvent.click(screen.getByRole("button", { name: /arrêter/i }));

    expect(invokeMock).toHaveBeenCalledWith("stop_stream");
  });

  it("should_return_to_the_offline_state_when_the_stream_stops", async () => {
    render(<LiveBar />);
    await waitFor(() => expect(listenMock).toHaveBeenCalled());
    emit({ type: "started" });

    emit({ type: "stream_stopped" });

    expect(screen.queryByText(/en direct/i)).toBeNull();
    expect(screen.getByRole("button", { name: /démarrer/i })).toBeTruthy();
  });

  it("should_show_dropped_frames_because_that_is_the_health_signal", async () => {
    render(<LiveBar />);
    await waitFor(() => expect(listenMock).toHaveBeenCalled());
    emit({ type: "started" });

    emit({ type: "frames", dropped: 12, total: 1800 });

    expect(screen.getByText(/12/)).toBeTruthy();
  });

  it("should_always_show_the_viewers_slot_so_its_place_is_known", async () => {
    // Jay, 2026-09-05 : « mets le compteur, mais n/a si aucun compte n'est connecté —
    // de cette manière je le vois tout de même et je sais où il est ». Montrer la case
    // renseigne ; inventer un zéro ment. Les deux ne se confondent pas.
    render(<LiveBar />);

    expect(await screen.findByText(/spectateurs/i)).toBeTruthy();
    expect(screen.getByText("n/a")).toBeTruthy();
  });

  it("should_explain_why_the_viewers_count_is_unavailable", async () => {
    // Une valeur morte sans raison est une impasse. Elle doit dire ce qui la remplirait.
    render(<LiveBar />);

    const slot = await screen.findByTitle(/aucun compte/i);
    expect(slot).toBeTruthy();
  });

  it("should_report_an_engine_error_that_answers_its_own_request", async () => {
    // Cas réel attendu tant que la clé de diffusion n'est pas câblée : le moteur refuse
    // le démarrage, et l'utilisateur doit lire pourquoi plutôt que voir un bouton sans effet.
    render(<LiveBar />);
    await waitFor(() => expect(listenMock).toHaveBeenCalled());

    await userEvent.click(screen.getByRole("button", { name: /démarrer/i }));
    emit({ type: "error", message: "cible RTMP absente" });

    expect(await screen.findByRole("alert")).toBeTruthy();
    expect(screen.getByText(/cible RTMP absente/)).toBeTruthy();
  });

  it("should_ignore_engine_errors_it_never_asked_for", async () => {
    // Vécu 2026-09-05 : « Monitor Capture existe déjà dans cette scène » s'affichait dans
    // la barre du direct. Le moteur émet ses erreurs sur UN seul canal ; c'est à chaque
    // écran de ne montrer que les réponses à SES propres demandes. Sinon la barre du
    // direct devient le dépotoir des erreurs de tout le cockpit.
    render(<LiveBar />);
    await waitFor(() => expect(listenMock).toHaveBeenCalled());

    emit({
      type: "error",
      message: "« Monitor Capture » existe déjà dans cette scène",
    });

    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("should_report_a_refused_command_from_the_controller", async () => {
    invokeMock.mockRejectedValue("le moteur n'est pas démarré");
    render(<LiveBar />);

    await userEvent.click(
      await screen.findByRole("button", { name: /démarrer/i }),
    );

    expect(await screen.findByRole("alert")).toBeTruthy();
  });
});

describe("formatElapsed", () => {
  // La durée est testée ici, sur la fonction PURE, et non en avançant une horloge
  // simulée dans le composant : ces horloges figeaient la suite complète, parce que
  // `userEvent` les attend et que le pool de vitest réutilise ses processus.
  it("should_pad_minutes_and_seconds_but_never_the_hours", () => {
    expect(formatElapsed(0)).toBe("0:00:00");
    expect(formatElapsed(65)).toBe("0:01:05");
    expect(formatElapsed(3725)).toBe("1:02:05");
  });

  it("should_keep_counting_past_ten_hours", () => {
    // Un direct long ne doit pas repartir à zéro ni tronquer.
    expect(formatElapsed(36_000)).toBe("10:00:00");
  });

  it("should_show_the_loss_rate_next_to_the_count", async () => {
    // Jay, 2026-09-07 : son seuil est un TAUX (2 %), pas un compte. Devant « 378 images
    // perdues » il ne pouvait pas juger seul — il a du me donner le nombre pour que je
    // fasse la division. Un cockpit qui oblige a calculer ne pilote pas.
    render(<LiveBar />);
    await waitFor(() => expect(listenMock).toHaveBeenCalled());
    emit({ type: "started" });

    emit({ type: "frames", dropped: 378, total: 54_000 });

    expect(screen.getByText(/0,7\s*%|0\.7\s*%/)).toBeTruthy();
  });

  it("should_colour_the_rate_by_how_bad_it_is", async () => {
    render(<LiveBar />);
    await waitFor(() => expect(listenMock).toHaveBeenCalled());
    emit({ type: "started" });

    emit({ type: "frames", dropped: 2_000, total: 54_000 });

    // Au-dessus du seuil de Jay : la couleur doit crier, pas chuchoter.
    const mesure = screen.getByTestId("taux-images-perdues");
    expect(mesure.className).toContain("hikari-red");
  });

  it("should_show_no_rate_before_a_single_frame_has_been_sent", async () => {
    // Zero image envoyee n'est pas zero pour cent de perte : c'est une absence de mesure.
    // Afficher « 0 % » au demarrage donnerait une assurance que rien ne soutient.
    render(<LiveBar />);
    await waitFor(() => expect(listenMock).toHaveBeenCalled());
    emit({ type: "started" });

    emit({ type: "frames", dropped: 0, total: 0 });

    expect(screen.queryByTestId("taux-images-perdues")).toBeNull();
  });
});
