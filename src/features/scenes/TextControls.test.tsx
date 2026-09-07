// @vitest-environment jsdom
//
// Tests écrits AVANT le composant (TDG).
//
// Jay, 2026-09-07 : « mettre une source de texte sans réglage, sans personnalisation, je
// trouve ça très inutile ». Ces tests fixent ce que le panneau doit permettre, et surtout
// ce qu'il doit ENVOYER au moteur — un curseur qui bouge sans rien transmettre serait la
// même fausse promesse que le bouton d'adaptation décoratif de ce matin.

import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { TextControls } from "./TextControls";
import { DEFAULT_TEXT_SETTINGS, type TextSettings } from "./textSettings";

const invokeMock = vi.hoisted(() => vi.fn().mockResolvedValue(undefined));
vi.mock("@tauri-apps/api/core", () => ({ invoke: invokeMock }));

const onChange = vi.fn();

/** Le composant est PILOTÉ par son parent : sans un parent qui retient l'état, taper deux
 * chiffres empilerait le second sur l'ancienne valeur. Le harnais reproduit donc le vrai
 * parent — un harnais qui ne se met pas à jour teste un composant qui n'existe pas. */
function Harnais({ initial }: { initial: TextSettings }) {
  const [settings, setSettings] = useState(initial);
  return (
    <TextControls
      scene="main"
      name="Mon titre"
      text="Mon titre"
      settings={settings}
      onChange={(next) => {
        setSettings(next);
        onChange(next);
      }}
    />
  );
}

function poser(settings = DEFAULT_TEXT_SETTINGS) {
  render(<Harnais initial={settings} />);
}

/** Ce que le moteur a réellement reçu au dernier appel. */
function dernierEnvoi() {
  const appels = invokeMock.mock.calls.filter(
    ([nom]) => nom === "set_text_settings",
  );
  return appels[appels.length - 1]?.[1] as
    | { scene: string; name: string; settings: typeof DEFAULT_TEXT_SETTINGS }
    | undefined;
}

beforeEach(() => {
  invokeMock.mockClear();
  onChange.mockClear();
});

afterEach(cleanup);

describe("TextControls", () => {
  it("should_send_the_new_size_to_the_engine", async () => {
    poser();

    const champ = screen.getByLabelText(/taille/i);
    await userEvent.clear(champ);
    await userEvent.type(champ, "96");
    // La valeur part quand l'utilisateur QUITTE le champ : borner a chaque frappe rendait
    // la saisie impossible (taper « 96 » apres avoir efface produisait 500).
    fireEvent.blur(champ);

    expect(dernierEnvoi()?.settings.size).toBe(96);
    expect(dernierEnvoi()?.scene).toBe("main");
    expect(dernierEnvoi()?.name).toBe("Mon titre");
  });

  it("should_send_the_new_colour_to_the_engine", async () => {
    poser();

    // Un sélecteur de couleur natif ne se tape pas au clavier : il émet un changement.
    fireEvent.change(screen.getByLabelText(/couleur du texte/i), {
      target: { value: "#ff0000" },
    });

    expect(dernierEnvoi()?.settings.color).toEqual({ r: 255, g: 0, b: 0 });
  });

  it("should_toggle_bold_and_say_so_to_the_engine", async () => {
    poser({ ...DEFAULT_TEXT_SETTINGS, bold: false });

    await userEvent.click(screen.getByRole("button", { name: /gras/i }));

    expect(dernierEnvoi()?.settings.bold).toBe(true);
  });

  it("should_turn_the_outline_off_when_asked", async () => {
    poser();

    await userEvent.click(screen.getByRole("button", { name: /contour/i }));

    expect(dernierEnvoi()?.settings.outline).toBe(false);
  });

  it("should_tell_the_caller_so_the_choice_can_be_remembered", async () => {
    // Sans cette remontée, les réglages s'appliqueraient à l'écran et disparaîtraient au
    // prochain lancement — la famille exacte que la persistance de session ferme.
    poser();

    await userEvent.click(screen.getByRole("button", { name: /italique/i }));

    expect(onChange).toHaveBeenCalled();
    const derniers = onChange.mock.calls;
    expect(derniers[derniers.length - 1]?.[0].italic).toBe(true);
  });

  it("should_refuse_a_size_that_would_make_the_text_vanish", async () => {
    poser();

    const champ = screen.getByLabelText(/taille/i);
    await userEvent.clear(champ);
    await userEvent.type(champ, "0");
    fireEvent.blur(champ);

    expect(dernierEnvoi()?.settings.size).toBeGreaterThan(0);
  });

  it("should_show_the_current_text_ready_to_edit", () => {
    poser();

    // `target_id` porte le texte : c'est là qu'il vit depuis l'ajout de la source.
    expect(screen.getByLabelText<HTMLInputElement>(/^texte$/i).value).toBe(
      "Mon titre",
    );
  });

  it("should_send_the_edited_text_to_the_engine_on_commit", async () => {
    poser();

    const champ = screen.getByLabelText(/^texte$/i);
    await userEvent.clear(champ);
    await userEvent.type(champ, "Nouveau titre");
    fireEvent.blur(champ);

    const appels = invokeMock.mock.calls.filter(
      ([nom]) => nom === "set_text_content",
    );
    const dernier = appels[appels.length - 1]?.[1];
    expect(dernier).toEqual({
      scene: "main",
      name: "Mon titre",
      text: "Nouveau titre",
    });
  });

  it("should_refuse_to_send_an_empty_text", async () => {
    // Un texte vide est un rectangle invisible que l'utilisateur chercherait dans sa scène
    // sans jamais le voir — la même garde qu'à l'ajout de la source.
    poser();

    const champ = screen.getByLabelText(/^texte$/i);
    await userEvent.clear(champ);
    fireEvent.blur(champ);

    const appels = invokeMock.mock.calls.filter(
      ([nom]) => nom === "set_text_content",
    );
    expect(appels).toHaveLength(0);
    expect(screen.getByLabelText<HTMLInputElement>(/^texte$/i).value).toBe(
      "Mon titre",
    );
  });
});
