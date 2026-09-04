// @vitest-environment jsdom
//
// Tests écrits AVANT les composants (TDG). Ce filet garde ce qui manque aujourd'hui à
// l'interface et que la maquette montre : des panneaux qui se ressemblent, des boutons
// qu'on peut viser et nommer, des états lisibles autrement que par la couleur.
//
// Deux exigences y sont vérifiées à chaque fois, parce qu'elles sont BLOQUANTES chez nous
// et qu'aucune ne se voit sur une capture d'écran :
//   - tout ce qui est interactif porte un nom accessible (lecteur d'écran, clavier) ;
//   - un état n'est jamais porté par la seule couleur (`aria-pressed`, `aria-current`).

import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { Badge } from "./Badge";
import { IconButton } from "./IconButton";
import { Panel } from "./Panel";
import { SectionTitle } from "./SectionTitle";
import { Segmented } from "./Segmented";

afterEach(cleanup);

describe("Panel", () => {
  it("should_expose_its_title_as_a_heading", () => {
    // Un titre de panneau doit être un vrai titre : c'est ce qui permet de naviguer de
    // panneau en panneau au clavier, et ce que la maquette dessine en haut de chaque carte.
    render(<Panel title="Scènes">contenu</Panel>);

    expect(screen.getByRole("heading", { name: "Scènes" })).toBeTruthy();
    expect(screen.getByText("contenu")).toBeTruthy();
  });

  it("should_render_a_badge_next_to_the_title_when_given_one", () => {
    render(
      <Panel title="Mixage audio" badge="écoute / diffusion">
        contenu
      </Panel>,
    );

    expect(screen.getByText("écoute / diffusion")).toBeTruthy();
  });

  it("should_render_its_actions_in_the_header", () => {
    render(
      <Panel title="Scènes" actions={<button type="button">Ajouter</button>}>
        contenu
      </Panel>,
    );

    expect(screen.getByRole("button", { name: "Ajouter" })).toBeTruthy();
  });
});

describe("SectionTitle", () => {
  it("should_expose_the_section_label_as_a_heading", () => {
    render(<SectionTitle>Sources</SectionTitle>);

    expect(screen.getByRole("heading", { name: "Sources" })).toBeTruthy();
  });
});

describe("Badge", () => {
  it("should_render_its_text", () => {
    render(<Badge>1 clic</Badge>);

    expect(screen.getByText("1 clic")).toBeTruthy();
  });

  it("should_name_the_live_state_in_words_not_only_in_red", () => {
    // Un badge « en direct » rouge est invisible pour qui ne distingue pas le rouge, et
    // muet pour un lecteur d'écran. Le mot porte l'information, la couleur l'appuie.
    render(<Badge tone="live">EN DIRECT</Badge>);

    expect(screen.getByText("EN DIRECT")).toBeTruthy();
  });
});

describe("IconButton", () => {
  it("should_carry_an_accessible_name_even_though_it_shows_only_an_icon", () => {
    // Les boutons actuels des scènes (↑ ↓ ✎ ✕) n'ont aucun nom : au clavier comme au
    // lecteur d'écran, ce sont quatre boutons identiques et muets.
    render(
      <IconButton label="Monter la scène" onClick={() => {}}>
        ↑
      </IconButton>,
    );

    expect(
      screen.getByRole("button", { name: "Monter la scène" }),
    ).toBeTruthy();
  });

  it("should_call_its_handler_on_click", async () => {
    const onClick = vi.fn();
    render(
      <IconButton label="Supprimer" onClick={onClick}>
        ✕
      </IconButton>,
    );

    await userEvent.click(screen.getByRole("button", { name: "Supprimer" }));

    expect(onClick).toHaveBeenCalledTimes(1);
  });

  it("should_announce_a_pressed_state_when_it_is_a_toggle", () => {
    render(
      <IconButton label="Afficher la source" pressed onClick={() => {}}>
        👁
      </IconButton>,
    );

    expect(
      screen
        .getByRole("button", { name: "Afficher la source" })
        .getAttribute("aria-pressed"),
    ).toBe("true");
  });

  it("should_not_fire_when_disabled", async () => {
    const onClick = vi.fn();
    render(
      <IconButton label="Monter" disabled onClick={onClick}>
        ↑
      </IconButton>,
    );

    await userEvent.click(screen.getByRole("button", { name: "Monter" }));

    expect(onClick).not.toHaveBeenCalled();
  });
});

describe("Segmented", () => {
  const OPTIONS = [
    { id: "setup", label: "Préparation" },
    { id: "live", label: "Live" },
  ];

  it("should_mark_the_selected_option_for_assistive_technology", () => {
    render(
      <Segmented
        label="Disposition"
        options={OPTIONS}
        value="live"
        onChange={() => {}}
      />,
    );

    expect(
      screen.getByRole("button", { name: "Live" }).getAttribute("aria-pressed"),
    ).toBe("true");
    expect(
      screen
        .getByRole("button", { name: "Préparation" })
        .getAttribute("aria-pressed"),
    ).toBe("false");
  });

  it("should_report_the_option_the_user_picked", async () => {
    const onChange = vi.fn();
    render(
      <Segmented
        label="Disposition"
        options={OPTIONS}
        value="live"
        onChange={onChange}
      />,
    );

    await userEvent.click(screen.getByRole("button", { name: "Préparation" }));

    expect(onChange).toHaveBeenCalledWith("setup");
  });

  it("should_group_its_options_under_the_given_label", () => {
    // Sans le nom du groupe, un lecteur d'écran annonce deux boutons isolés et jamais
    // « Disposition : Live » — l'utilisateur ne sait pas de quel réglage il s'agit.
    render(
      <Segmented
        label="Disposition"
        options={OPTIONS}
        value="live"
        onChange={() => {}}
      />,
    );

    expect(screen.getByRole("group", { name: "Disposition" })).toBeTruthy();
  });
});
