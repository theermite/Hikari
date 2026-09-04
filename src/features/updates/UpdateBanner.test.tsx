// @vitest-environment jsdom
//
// Tests écrits AVANT le composant (TDG). Ce que ce filet garde, dans l'ordre où ça compte
// pour l'utilisateur : le cockpit ne casse jamais à cause du canal de mise à jour, rien ne
// s'affiche quand il n'y a rien à annoncer, et une mise à jour n'est JAMAIS installée sans
// un clic (Dignity — zéro action subie).

import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { UpdateBanner } from "./UpdateBanner";

const checkMock = vi.hoisted(() => vi.fn());
vi.mock("@tauri-apps/plugin-updater", () => ({ check: checkMock }));

const relaunchMock = vi.hoisted(() => vi.fn());
vi.mock("@tauri-apps/plugin-process", () => ({ relaunch: relaunchMock }));

/** Une mise à jour telle que le module la renvoie — seuls les champs que l'écran lit. */
function update(overrides: Record<string, unknown> = {}) {
  return {
    version: "0.2.0",
    body: "Mixeur audio : ducking",
    downloadAndInstall: vi.fn().mockResolvedValue(undefined),
    ...overrides,
  };
}

beforeEach(() => {
  checkMock.mockReset();
  relaunchMock.mockReset();
});

afterEach(cleanup);

describe("UpdateBanner", () => {
  it("should_render_nothing_when_no_update_is_available", async () => {
    checkMock.mockResolvedValue(null);

    const { container } = render(<UpdateBanner />);

    await waitFor(() => expect(checkMock).toHaveBeenCalled());
    expect(container).toBeEmptyDOMElement();
  });

  it("should_render_nothing_when_the_channel_is_unreachable", async () => {
    // Hors ligne, canal privé absent, endpoint mal configuré : le cockpit doit continuer
    // exactement comme si de rien n'était. Une panne du canal de MAJ n'est jamais une
    // panne de l'app (Let It Crash : la faute reste isolée là où elle naît).
    checkMock.mockRejectedValue(new Error("network unreachable"));

    const { container } = render(<UpdateBanner />);

    await waitFor(() => expect(checkMock).toHaveBeenCalled());
    expect(container).toBeEmptyDOMElement();
  });

  it("should_announce_the_new_version_when_an_update_is_available", async () => {
    checkMock.mockResolvedValue(update({ version: "0.4.1" }));

    render(<UpdateBanner />);

    expect(await screen.findByText(/0\.4\.1/)).toBeTruthy();
  });

  it("should_install_only_after_the_user_clicks", async () => {
    const available = update();
    checkMock.mockResolvedValue(available);

    render(<UpdateBanner />);
    await screen.findByText(/0\.2\.0/);

    // Rien ne doit avoir bougé tant que personne n'a cliqué.
    expect(available.downloadAndInstall).not.toHaveBeenCalled();

    await userEvent.click(
      screen.getByRole("button", { name: /mettre à jour/i }),
    );

    await waitFor(() =>
      expect(available.downloadAndInstall).toHaveBeenCalled(),
    );
  });

  it("should_relaunch_the_app_once_the_update_is_installed", async () => {
    const available = update();
    checkMock.mockResolvedValue(available);

    render(<UpdateBanner />);
    await screen.findByText(/0\.2\.0/);
    await userEvent.click(
      screen.getByRole("button", { name: /mettre à jour/i }),
    );

    await waitFor(() => expect(relaunchMock).toHaveBeenCalled());
  });

  it("should_keep_the_banner_and_report_when_the_download_fails", async () => {
    // Un échec de téléchargement ne doit ni relancer l'app ni effacer l'annonce en
    // silence : l'utilisateur doit pouvoir réessayer et savoir pourquoi.
    const available = update({
      downloadAndInstall: vi
        .fn()
        .mockRejectedValue(new Error("coupure réseau")),
    });
    checkMock.mockResolvedValue(available);

    render(<UpdateBanner />);
    await screen.findByText(/0\.2\.0/);
    await userEvent.click(
      screen.getByRole("button", { name: /mettre à jour/i }),
    );

    expect(await screen.findByRole("alert")).toBeTruthy();
    expect(relaunchMock).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: /mettre à jour/i })).toBeTruthy();
  });

  it("should_hide_the_banner_when_the_user_dismisses_it", async () => {
    const available = update();
    checkMock.mockResolvedValue(available);

    render(<UpdateBanner />);
    await screen.findByText(/0\.2\.0/);

    await userEvent.click(screen.getByRole("button", { name: /plus tard/i }));

    expect(screen.queryByText(/0\.2\.0/)).toBeNull();
    expect(available.downloadAndInstall).not.toHaveBeenCalled();
  });
});
