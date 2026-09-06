// @vitest-environment jsdom
//
// Tests écrits AVANT le composant (TDG).
//
// Ce que ce bandeau existe pour régler, constaté le 2026-09-06 : le moteur REFUSE certaines
// demandes (« ce n'est pas une source retirable de cette scène », une caméra qu'il n'ouvre
// pas), et ce refus n'arrivait nulle part. Le clic ne faisait rien, en silence, et il était
// impossible de dire si l'échec venait du matériel ou du logiciel.
//
// Un refus arrive de façon ASYNCHRONE, longtemps après le clic, et souvent pendant qu'un
// autre panneau est au premier plan. C'est pourquoi il se lit au-dessus du cockpit entier
// plutôt que dans le panneau d'où partait la demande.

import { act, cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { EngineErrorBanner } from "./EngineErrorBanner";

let listener: ((event: { payload: unknown }) => void) | null = null;
const listenMock = vi.hoisted(() => vi.fn());
vi.mock("@tauri-apps/api/event", () => ({ listen: listenMock }));

function emit(payload: unknown) {
  act(() => {
    listener?.({ payload });
  });
}

beforeEach(() => {
  listener = null;
  listenMock.mockReset();
  listenMock.mockImplementation((_name: string, handler: typeof listener) => {
    listener = handler;
    return Promise.resolve(() => {});
  });
});

afterEach(cleanup);

describe("EngineErrorBanner", () => {
  it("should_stay_silent_when_the_engine_has_refused_nothing", async () => {
    render(<EngineErrorBanner />);
    await waitFor(() => expect(listenMock).toHaveBeenCalled());

    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("should_show_the_refusal_when_the_engine_reports_an_error", async () => {
    render(<EngineErrorBanner />);
    await waitFor(() => expect(listenMock).toHaveBeenCalled());

    emit({
      type: "error",
      message: "« Webcam » n'est pas une source retirable de cette scène",
    });

    expect(screen.getByRole("alert").textContent).toContain(
      "n'est pas une source retirable",
    );
  });

  it("should_show_the_latest_refusal_when_a_second_one_arrives", async () => {
    render(<EngineErrorBanner />);
    await waitFor(() => expect(listenMock).toHaveBeenCalled());

    emit({ type: "error", message: "premier refus" });
    emit({ type: "error", message: "second refus" });

    const alert = screen.getByRole("alert");
    expect(alert.textContent).toContain("second refus");
    expect(alert.textContent).not.toContain("premier refus");
  });

  it("should_hide_the_refusal_when_it_is_dismissed", async () => {
    const user = userEvent.setup();
    render(<EngineErrorBanner />);
    await waitFor(() => expect(listenMock).toHaveBeenCalled());
    emit({ type: "error", message: "un refus" });

    await user.click(screen.getByRole("button", { name: /fermer/i }));

    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("should_show_a_new_refusal_after_the_previous_one_was_dismissed", async () => {
    const user = userEvent.setup();
    render(<EngineErrorBanner />);
    await waitFor(() => expect(listenMock).toHaveBeenCalled());
    emit({ type: "error", message: "un refus" });
    await user.click(screen.getByRole("button", { name: /fermer/i }));

    // Même texte que le refus déjà écarté : le second clic a bien été refusé lui aussi, et
    // le taire donnerait exactement le silence que ce bandeau existe pour supprimer.
    emit({ type: "error", message: "un refus" });

    expect(screen.getByRole("alert").textContent).toContain("un refus");
  });

  it("should_ignore_an_error_that_carries_no_text", async () => {
    render(<EngineErrorBanner />);
    await waitFor(() => expect(listenMock).toHaveBeenCalled());

    emit({ type: "error" });

    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("should_ignore_messages_that_are_not_refusals", async () => {
    render(<EngineErrorBanner />);
    await waitFor(() => expect(listenMock).toHaveBeenCalled());

    emit({ type: "scene_list", active: "main", scenes: [] });

    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("should_name_the_platform_when_one_streaming_target_fails", async () => {
    render(<EngineErrorBanner />);
    await waitFor(() => expect(listenMock).toHaveBeenCalled());

    // Un échec par plateforme (B3) est un refus comme un autre pour l'utilisateur : sans
    // lui, une diffusion peut tomber sur Twitch pendant que YouTube continue, sans un mot.
    emit({
      type: "platform_error",
      id: "twitch",
      message: "cible RTMP refusée",
    });

    const alert = screen.getByRole("alert");
    expect(alert.textContent).toContain("twitch");
    expect(alert.textContent).toContain("cible RTMP refusée");
  });
});
