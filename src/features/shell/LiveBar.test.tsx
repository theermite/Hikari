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

const invokeMock = vi.hoisted(() => vi.fn().mockResolvedValue(undefined));
vi.mock("@tauri-apps/api/core", () => ({ invoke: invokeMock }));

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
  invokeMock.mockResolvedValue(undefined);
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

    expect(invokeMock).toHaveBeenCalledWith("start_stream");
    expect(screen.queryByText(/en direct/i)).toBeNull();
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

  it("should_report_an_engine_error_instead_of_failing_silently", async () => {
    // Cas réel attendu tant que la clé de diffusion n'est pas câblée : le moteur refuse,
    // et l'utilisateur doit lire pourquoi plutôt que voir un bouton sans effet.
    render(<LiveBar />);
    await waitFor(() => expect(listenMock).toHaveBeenCalled());

    emit({ type: "error", message: "cible RTMP absente" });

    expect(await screen.findByRole("alert")).toBeTruthy();
    expect(screen.getByText(/cible RTMP absente/)).toBeTruthy();
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
});
