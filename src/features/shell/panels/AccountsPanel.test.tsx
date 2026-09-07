// @vitest-environment jsdom
//
// Tests écrits AVANT la correction (TDG).
//
// Le défaut que ces tests ferment, constaté par Jay le 2026-09-07 : « je me connecte à
// Twitch, j'ai la confirmation, mais dès que je sors des paramètres, c'est comme si la
// connexion se coupait ».
//
// Rien n'était cassé côté connexion. L'écran repartait de « pas connecté » à chaque
// affichage, et ne passait au vert que sur l'événement `twitch-connected` du moment. Un
// écran qui ne DEMANDE jamais l'état ne peut que l'oublier — le jeton, lui, était resté
// dans le coffre tout du long.

import { cleanup, render, screen, waitFor } from "@testing-library/react";
import type { IDockviewPanelProps } from "dockview-react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AccountsPanel } from "./AccountsPanel";

const invokeMock = vi.hoisted(() => vi.fn());
const listenMock = vi.hoisted(() => vi.fn());
vi.mock("@tauri-apps/api/core", () => ({ invoke: invokeMock }));
vi.mock("@tauri-apps/api/event", () => ({ listen: listenMock }));

const panelProps = {} as IDockviewPanelProps;

beforeEach(() => {
  invokeMock.mockReset();
  listenMock.mockReset();
  listenMock.mockImplementation(() => Promise.resolve(() => {}));
});

afterEach(cleanup);

describe("AccountsPanel", () => {
  it("should_show_twitch_connected_when_a_token_is_already_stored", async () => {
    invokeMock.mockResolvedValue({ twitch: true, youtube: false });

    render(<AccountsPanel {...panelProps} />);

    await waitFor(() => {
      expect(screen.getByText(/Compte Twitch connecté/)).toBeTruthy();
    });
    expect(invokeMock).toHaveBeenCalledWith("account_status");
  });

  it("should_show_youtube_connected_when_a_token_is_already_stored", async () => {
    invokeMock.mockResolvedValue({ twitch: false, youtube: true });

    render(<AccountsPanel {...panelProps} />);

    await waitFor(() => {
      expect(screen.getByText(/Compte YouTube connecté/)).toBeTruthy();
    });
  });

  it("should_stay_idle_when_no_account_is_stored", async () => {
    invokeMock.mockResolvedValue({ twitch: false, youtube: false });

    render(<AccountsPanel {...panelProps} />);

    await waitFor(() => {
      expect(invokeMock).toHaveBeenCalledWith("account_status");
    });
    expect(screen.queryByText(/Compte Twitch connecté/)).toBeNull();
    expect(screen.queryByText(/Compte YouTube connecté/)).toBeNull();
  });

  it("should_stay_usable_when_the_status_read_fails", async () => {
    // Un coffre illisible ne doit pas laisser l'écran muet : le bouton reste cliquable,
    // sinon un défaut de lecture enfermerait l'utilisateur hors de son propre compte.
    invokeMock.mockRejectedValue("coffre illisible");

    render(<AccountsPanel {...panelProps} />);

    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: /Connecter Twitch/ }),
      ).toBeTruthy();
    });
    expect(
      (
        screen.getByRole("button", {
          name: /Connecter Twitch/,
        }) as HTMLButtonElement
      ).disabled,
    ).toBe(false);
  });

  it("should_read_the_stored_status_only_once", async () => {
    // Garde contre un défaut introduit en corrigeant celui-ci : si la fonction passée à
    // l'effet est recréée à chaque rendu, l'effet se relance, écrit l'état, provoque un
    // rendu, et la lecture part en boucle sans fin. Le symptôme serait un écran figé et un
    // coffre système sollicité en continu — cher, et invisible dans un test qui n'attend
    // qu'un seul appel.
    invokeMock.mockResolvedValue({ twitch: true, youtube: true });

    render(<AccountsPanel {...panelProps} />);

    await waitFor(() => {
      expect(screen.getByText(/Compte Twitch connecté/)).toBeTruthy();
    });
    await new Promise((resolve) => setTimeout(resolve, 50));

    const reads = invokeMock.mock.calls.filter(
      ([name]) => name === "account_status",
    );
    expect(reads).toHaveLength(1);
  });
});
