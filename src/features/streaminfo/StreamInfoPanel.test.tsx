// @vitest-environment jsdom
//
// Tests écrits AVANT le composant (TDG). Ce que ce filet garde : le titre/tags/catégorie
// se pré-remplissent depuis Twitch, le titre vide ou trop long bloque « Publier », un
// tag au-delà de 10 ne s'ajoute pas, et seuls les champs réellement changés partent dans
// la mise à jour (jamais un patch qui réécrit tout, même ce qui n'a pas bougé).

import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { IDockviewPanelProps } from "dockview-react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import * as api from "./api";
import { StreamInfoPanel } from "./StreamInfoPanel";

vi.mock("./api");

function props(): IDockviewPanelProps {
  return {} as IDockviewPanelProps;
}

function channelInfo(
  overrides: Partial<Awaited<ReturnType<typeof api.getStreamInfo>>> = {},
) {
  return {
    title: "Session de dev",
    game_id: "509658",
    game_name: "Just Chatting",
    tags: ["Francais"],
    ...overrides,
  };
}

beforeEach(() => {
  vi.mocked(api.getStreamInfo).mockReset();
  vi.mocked(api.searchCategories).mockReset();
  vi.mocked(api.updateStreamInfo).mockReset();
  vi.mocked(api.getStreamInfo).mockResolvedValue(channelInfo());
  // Le volet YouTube (`YoutubeSection`) vit dans le même panneau — ces tests ne parlent
  // que de Twitch, mais le composant monte les deux. Résolu par défaut pour ne pas le
  // laisser planter sur un appel non mocké ; son propre comportement est testé à part,
  // dans YoutubeSection.test.tsx.
  vi.mocked(api.getYoutubeStreamInfo).mockReset();
  vi.mocked(api.getYoutubeCategories).mockReset();
  vi.mocked(api.updateYoutubeStreamInfo).mockReset();
  vi.mocked(api.getYoutubeStreamInfo).mockResolvedValue({
    title: "",
    description: "",
    category_id: "",
    tags: [],
  });
  vi.mocked(api.getYoutubeCategories).mockResolvedValue([]);
});

afterEach(cleanup);

describe("StreamInfoPanel", () => {
  it("should_prefill_title_category_and_tags_from_twitch", async () => {
    render(<StreamInfoPanel {...props()} />);

    expect(
      await screen.findByDisplayValue("Session de dev"),
    ).toBeInTheDocument();
    expect(screen.getByDisplayValue("Just Chatting")).toBeInTheDocument();
    expect(screen.getByText("Francais")).toBeInTheDocument();
  });

  it("should_show_the_load_error_instead_of_an_empty_form_when_twitch_refuses", async () => {
    vi.mocked(api.getStreamInfo).mockReset();
    vi.mocked(api.getStreamInfo).mockRejectedValue(
      "connecte ton compte Twitch dans Paramètres",
    );

    render(<StreamInfoPanel {...props()} />);

    expect(
      await screen.findByText("connecte ton compte Twitch dans Paramètres"),
    ).toBeInTheDocument();
    expect(screen.queryByLabelText("Titre")).not.toBeInTheDocument();
  });

  it("should_disable_publish_when_the_title_is_emptied", async () => {
    const user = userEvent.setup();
    render(<StreamInfoPanel {...props()} />);
    const title = await screen.findByDisplayValue("Session de dev");

    await user.clear(title);

    expect(
      screen.getByRole("button", { name: /publier sur twitch/i }),
    ).toBeDisabled();
  });

  it("should_disable_publish_when_the_title_exceeds_140_characters", async () => {
    const user = userEvent.setup();
    render(<StreamInfoPanel {...props()} />);
    const title = await screen.findByDisplayValue("Session de dev");

    await user.clear(title);
    await user.type(title, "x".repeat(141));

    expect(
      screen.getByRole("button", { name: /publier sur twitch/i }),
    ).toBeDisabled();
  });

  it("should_add_a_tag_on_enter_and_remove_it_on_click", async () => {
    const user = userEvent.setup();
    render(<StreamInfoPanel {...props()} />);
    await screen.findByDisplayValue("Session de dev");

    // Par le label, pas le placeholder : les volets Twitch et YouTube partagent le même
    // texte de placeholder, seul le label Twitch porte le compte "(n/10)".
    const tagInput = screen.getByLabelText(/tags \(/i);
    await user.type(tagInput, "Speedrun{Enter}");

    expect(screen.getByText("Speedrun")).toBeInTheDocument();

    await user.click(screen.getByLabelText("Retirer le tag Speedrun"));

    expect(screen.queryByText("Speedrun")).not.toBeInTheDocument();
  });

  it("should_refuse_an_eleventh_tag", async () => {
    vi.mocked(api.getStreamInfo).mockResolvedValue(
      channelInfo({ tags: Array.from({ length: 10 }, (_, i) => `tag${i}`) }),
    );
    render(<StreamInfoPanel {...props()} />);
    await screen.findByDisplayValue("Session de dev");

    expect(screen.getByPlaceholderText("Maximum atteint")).toBeDisabled();
  });

  it("should_publish_only_the_changed_fields", async () => {
    const user = userEvent.setup();
    vi.mocked(api.updateStreamInfo).mockResolvedValue(undefined);
    render(<StreamInfoPanel {...props()} />);
    const title = await screen.findByDisplayValue("Session de dev");

    await user.clear(title);
    await user.type(title, "Nouveau titre");
    await user.click(
      screen.getByRole("button", { name: /publier sur twitch/i }),
    );

    await waitFor(() => {
      expect(api.updateStreamInfo).toHaveBeenCalledExactlyOnceWith({
        title: "Nouveau titre",
      });
    });
  });

  it("should_show_a_save_error_when_twitch_refuses_the_update", async () => {
    const user = userEvent.setup();
    vi.mocked(api.updateStreamInfo).mockRejectedValue(
      "Twitch a refusé (401) : scope manquant",
    );
    render(<StreamInfoPanel {...props()} />);
    const title = await screen.findByDisplayValue("Session de dev");

    await user.type(title, "!");
    await user.click(
      screen.getByRole("button", { name: /publier sur twitch/i }),
    );

    expect(
      await screen.findByText("Twitch a refusé (401) : scope manquant"),
    ).toBeInTheDocument();
  });
});
