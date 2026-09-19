// @vitest-environment jsdom
//
// Tests écrits AVANT le composant (TDG) — miroir de StreamInfoPanel.test.tsx côté
// Twitch, adapté aux différences réelles : une description en plus, une catégorie en
// menu fermé (pas de recherche), pas de limite de nombre de tags côté YouTube.

import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import * as api from "./api";
import { YoutubeSection } from "./YoutubeSection";

vi.mock("./api");

function videoInfo(
  overrides: Partial<Awaited<ReturnType<typeof api.getYoutubeStreamInfo>>> = {},
) {
  return {
    title: "Session de dev",
    description: "On code le volet YouTube.",
    category_id: "20",
    tags: ["Francais"],
    ...overrides,
  };
}

beforeEach(() => {
  vi.mocked(api.getYoutubeStreamInfo).mockReset();
  vi.mocked(api.getYoutubeCategories).mockReset();
  vi.mocked(api.updateYoutubeStreamInfo).mockReset();
  vi.mocked(api.getYoutubeStreamInfo).mockResolvedValue(videoInfo());
  vi.mocked(api.getYoutubeCategories).mockResolvedValue([
    { id: "20", name: "Gaming" },
    { id: "24", name: "Entertainment" },
  ]);
});

afterEach(cleanup);

describe("YoutubeSection", () => {
  it("should_prefill_title_description_category_and_tags_from_youtube", async () => {
    render(<YoutubeSection />);

    expect(
      await screen.findByDisplayValue("Session de dev"),
    ).toBeInTheDocument();
    expect(
      screen.getByDisplayValue("On code le volet YouTube."),
    ).toBeInTheDocument();
    expect(screen.getByText("Francais")).toBeInTheDocument();
    expect(screen.getByLabelText("Catégorie")).toHaveValue("20");
  });

  it("should_show_the_load_error_instead_of_an_empty_form_when_youtube_refuses", async () => {
    vi.mocked(api.getYoutubeStreamInfo).mockReset();
    vi.mocked(api.getYoutubeStreamInfo).mockRejectedValue(
      "connecte ton compte YouTube dans Paramètres",
    );

    render(<YoutubeSection />);

    expect(
      await screen.findByText("connecte ton compte YouTube dans Paramètres"),
    ).toBeInTheDocument();
    expect(screen.queryByLabelText("Titre")).not.toBeInTheDocument();
  });

  it("should_disable_publish_when_the_title_is_emptied", async () => {
    const user = userEvent.setup();
    render(<YoutubeSection />);
    const title = await screen.findByDisplayValue("Session de dev");

    await user.clear(title);

    expect(
      screen.getByRole("button", { name: /publier sur youtube/i }),
    ).toBeDisabled();
  });

  it("should_disable_publish_when_the_description_exceeds_5000_characters", async () => {
    render(<YoutubeSection />);
    const description = await screen.findByDisplayValue(
      "On code le volet YouTube.",
    );

    // `fireEvent.change` plutôt que `user.type` : 5001 frappes simulées une à une
    // dépassaient le délai du test et laissaient une frappe en cours fuiter sur le test
    // suivant (constaté — deux tests suivants recevaient un titre entrelacé de "x").
    // Le comportement testé ici est la limite, pas la saisie caractère par caractère.
    fireEvent.change(description, { target: { value: "x".repeat(5001) } });

    expect(
      screen.getByRole("button", { name: /publier sur youtube/i }),
    ).toBeDisabled();
  });

  it("should_add_a_tag_on_enter_and_remove_it_on_click", async () => {
    const user = userEvent.setup();
    render(<YoutubeSection />);
    await screen.findByDisplayValue("Session de dev");

    const tagInput = screen.getByPlaceholderText(/ajouter un tag/i);
    await user.type(tagInput, "Speedrun{Enter}");

    expect(screen.getByText("Speedrun")).toBeInTheDocument();

    await user.click(screen.getByLabelText("Retirer le tag Speedrun"));

    expect(screen.queryByText("Speedrun")).not.toBeInTheDocument();
  });

  it("should_still_show_the_form_when_only_the_category_list_fails", async () => {
    // Deux lectures indépendantes (voir le composant) : la liste des catégories ne doit
    // pas priver l'écran du reste si elle échoue seule.
    vi.mocked(api.getYoutubeCategories).mockReset();
    vi.mocked(api.getYoutubeCategories).mockRejectedValue("indisponible");

    render(<YoutubeSection />);

    expect(
      await screen.findByDisplayValue("Session de dev"),
    ).toBeInTheDocument();
  });

  it("should_publish_only_the_changed_fields", async () => {
    const user = userEvent.setup();
    vi.mocked(api.updateYoutubeStreamInfo).mockResolvedValue(undefined);
    render(<YoutubeSection />);
    const title = await screen.findByDisplayValue("Session de dev");

    await user.clear(title);
    await user.type(title, "Nouveau titre");
    await user.click(
      screen.getByRole("button", { name: /publier sur youtube/i }),
    );

    await waitFor(() => {
      expect(api.updateYoutubeStreamInfo).toHaveBeenCalledExactlyOnceWith({
        title: "Nouveau titre",
      });
    });
  });

  it("should_show_a_save_error_when_youtube_refuses_the_update", async () => {
    const user = userEvent.setup();
    vi.mocked(api.updateYoutubeStreamInfo).mockRejectedValue(
      "YouTube a refusé (401) : scope manquant",
    );
    render(<YoutubeSection />);
    const title = await screen.findByDisplayValue("Session de dev");

    await user.type(title, "!");
    await user.click(
      screen.getByRole("button", { name: /publier sur youtube/i }),
    );

    expect(
      await screen.findByText("YouTube a refusé (401) : scope manquant"),
    ).toBeInTheDocument();
  });
});
