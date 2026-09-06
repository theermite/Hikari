// @vitest-environment jsdom
//
// Le numéro de version dans le cockpit (2026-09-06).
//
// Pourquoi il existe : Jay ne pouvait pas savoir s'il était à jour. Il installe une fois
// et reçoit ensuite les mises à jour dans l'app — mais rien à l'écran ne disait quelle
// version tournait, ni si le canal avait répondu. Sans ça, la seule façon de vérifier
// était de réinstaller, ce qui est exactement ce que la mise à jour dans l'app évite.
//
// Ce que ces tests protègent : le numéro est toujours là, et l'état affiché correspond à
// ce que le canal a VRAIMENT répondu — « à jour » n'est jamais inventé quand le canal
// n'a pas pu être joint.

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { forgetUpdateCheck } from "./useUpdateCheck";
import { VersionTag } from "./VersionTag";

const checkMock = vi.hoisted(() => vi.fn());
vi.mock("@tauri-apps/plugin-updater", () => ({ check: checkMock }));

describe("VersionTag", () => {
  beforeEach(() => {
    forgetUpdateCheck();
    checkMock.mockReset();
    vi.spyOn(console, "warn").mockImplementation(() => {});
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("should_always_show_the_version_that_is_running", async () => {
    checkMock.mockResolvedValue(null);

    render(<VersionTag />);

    expect(await screen.findByText(`v${__APP_VERSION__}`)).toBeTruthy();
  });

  it("should_say_up_to_date_when_the_channel_answered_and_found_nothing", async () => {
    checkMock.mockResolvedValue(null);

    render(<VersionTag />);

    expect(await screen.findByText(/à jour/i)).toBeTruthy();
  });

  it("should_announce_a_new_version_when_the_channel_offers_one", async () => {
    checkMock.mockResolvedValue({ version: "0.5.0" });

    render(<VersionTag />);

    expect(await screen.findByText(/0\.5\.0 disponible/i)).toBeTruthy();
  });

  /// Le cas qui compte le plus : hors ligne, on ne SAIT pas si une version existe.
  /// Afficher « à jour » serait inventer une réponse que personne n'a donnée.
  it("should_never_claim_up_to_date_when_the_channel_could_not_be_reached", async () => {
    checkMock.mockRejectedValue(new Error("offline"));

    render(<VersionTag />);

    expect(await screen.findByText(/pas joignable/i)).toBeTruthy();
    expect(screen.queryByText(/à jour/i)).toBeNull();
  });
});
