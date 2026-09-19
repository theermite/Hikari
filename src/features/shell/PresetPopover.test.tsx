// @vitest-environment jsdom
//
// Tests écrits AVANT le déplacement du contenu (TDG). Ce que ce filet garde : le contenu
// Twitch/YouTube ne se monte (et n'appelle donc le backend) qu'à l'ouverture — jamais au
// seul affichage de la barre du direct — et le bouton ouvre/ferme la modale.

import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import * as api from "../streaminfo/api";
import { PresetPopover } from "./PresetPopover";

vi.mock("../streaminfo/api");

beforeEach(() => {
  vi.mocked(api.getStreamInfo).mockReset();
  vi.mocked(api.searchCategories).mockReset();
  vi.mocked(api.updateStreamInfo).mockReset();
  vi.mocked(api.getYoutubeStreamInfo).mockReset();
  vi.mocked(api.getYoutubeCategories).mockReset();
  vi.mocked(api.updateYoutubeStreamInfo).mockReset();
  // Jamais résolu par défaut : ces tests vérifient si l'appel PART, pas ce qu'il répond.
  vi.mocked(api.getStreamInfo).mockImplementation(() => new Promise(() => {}));
  vi.mocked(api.getYoutubeStreamInfo).mockImplementation(
    () => new Promise(() => {}),
  );
  vi.mocked(api.getYoutubeCategories).mockImplementation(
    () => new Promise(() => {}),
  );
});

afterEach(cleanup);

describe("PresetPopover", () => {
  it("should_not_call_the_backend_before_the_button_is_clicked", () => {
    render(<PresetPopover />);

    expect(api.getStreamInfo).not.toHaveBeenCalled();
    expect(api.getYoutubeStreamInfo).not.toHaveBeenCalled();
  });

  it("should_open_the_dialog_and_load_both_platforms_when_clicked", async () => {
    const user = userEvent.setup();
    render(<PresetPopover />);

    await user.click(screen.getByRole("button", { name: /préréglage/i }));

    expect(await screen.findByRole("dialog")).toBeTruthy();
    expect(api.getStreamInfo).toHaveBeenCalledOnce();
    expect(api.getYoutubeStreamInfo).toHaveBeenCalledOnce();
  });

  it("should_close_the_dialog_on_the_close_button", async () => {
    const user = userEvent.setup();
    render(<PresetPopover />);
    await user.click(screen.getByRole("button", { name: /préréglage/i }));
    await screen.findByRole("dialog");

    await user.click(screen.getByRole("button", { name: /fermer/i }));

    expect(screen.queryByRole("dialog")).toBeNull();
  });
});
