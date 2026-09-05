// @vitest-environment jsdom
//
// Filet de non-régression AVANT découpage de AudioPanel.tsx (558 lignes, au-dessus du
// plafond BLOQUANT de 500 — Quality.md). Rendu tel quel jusqu'ici, ce composant n'avait
// aucun test — même situation que MultiTask dans Shinkofa-Shared le 2026-08-19.
//
// Le moteur audio parle par deux canaux : un événement `engine-message` (Tauri) que le
// panneau écoute pour recevoir la liste des appareils et des sources, et des appels
// `invoke` pour agir dessus (ajouter, couper, régler le volume). Les deux sont simulés
// ici — aucun moteur réel n'est nécessaire pour prouver le comportement du panneau.

import { act, cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { IDockviewPanelProps } from "dockview-react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { requestAdd } from "../shell/panelActions";
import { AudioPanel } from "./AudioPanel";
import type { AudioEngineMessage, AudioSourceInfo } from "./types";

const invokeMock = vi.hoisted(() => vi.fn().mockResolvedValue(undefined));
vi.mock("@tauri-apps/api/core", () => ({ invoke: invokeMock }));

let engineListener: ((event: { payload: AudioEngineMessage }) => void) | null =
  null;
const listenMock = vi.hoisted(() => vi.fn());
vi.mock("@tauri-apps/api/event", () => ({ listen: listenMock }));

/** Simule le moteur qui répond — le seul chemin par lequel ce panneau reçoit des données.
 * Enveloppé dans `act()` : le panneau met à jour son état hors du cycle de rendu de React
 * Testing Library, qui doit donc être prévenu explicitement d'attendre le prochain rendu. */
function emit(message: AudioEngineMessage) {
  act(() => {
    engineListener?.({ payload: message });
  });
}

function source(overrides: Partial<AudioSourceInfo> = {}): AudioSourceInfo {
  return {
    name: "Micro USB",
    kind: "input",
    device_id: "dev-1",
    volume_percent: 80,
    monitor_volume_percent: 50,
    muted: false,
    monitoring: "none",
    noise_suppression: false,
    noise_method: "rnnoise",
    noise_level_db: -30,
    ...overrides,
  };
}

beforeEach(() => {
  invokeMock.mockClear();
  engineListener = null;
  listenMock.mockImplementation((_event: string, cb: typeof engineListener) => {
    engineListener = cb;
    return Promise.resolve(() => {});
  });
});

afterEach(() => {
  cleanup();
});

describe("AudioPanel", () => {
  it("should_afficher_un_message_d_attente_avant_que_le_moteur_reponde", () => {
    render(<AudioPanel {...({} as IDockviewPanelProps)} />);

    expect(
      screen.getByText(/Ouvre le panneau Aperçu pour gérer le son/i),
    ).toBeInTheDocument();
  });

  it("should_offer_to_add_a_track_without_listing_every_device", async () => {
    // Les appareils ne sont plus etales en permanence : la machine de Jay en expose une
    // douzaine, et les montrer tous remplissait le mixeur d'un choix qu'on ne fait qu'une
    // fois par appareil (2026-09-05). Un bouton ouvre la liste, a la demande.
    render(<AudioPanel {...({} as IDockviewPanelProps)} />);

    emit({
      type: "audio_devices",
      inputs: [{ name: "Micro USB", device_id: "dev-1" }],
      outputs: [],
    });

    // La liste vit dans une fenetre FERMEE : elle est dans le document (jsdom ne masque
    // pas un `<dialog>` clos) mais l'utilisateur ne la voit pas. Un `<dialog>` ferme ne
    // porte pas le role « dialog » : on interroge donc l'element lui-meme.
    expect(document.querySelector("dialog")?.hasAttribute("open")).toBe(false);
    expect(
      screen.queryByText(/Ouvre le panneau Aperçu/i),
    ).not.toBeInTheDocument();
  });

  it("should_ajouter_une_source_quand_on_choisit_un_appareil", async () => {
    const user = userEvent.setup();
    render(<AudioPanel {...({} as IDockviewPanelProps)} />);
    emit({
      type: "audio_devices",
      inputs: [{ name: "Micro USB", device_id: "dev-1" }],
      outputs: [],
    });

    // Le « + » vit dans l'ONGLET, dessine hors de ce panneau : le test emprunte donc le
    // meme chemin que lui, la demande d'ajout.
    act(() => requestAdd("audio"));
    await user.click(screen.getByRole("button", { name: "Micro USB" }));

    expect(invokeMock).toHaveBeenCalledWith("add_audio_source", {
      deviceId: "dev-1",
      kind: "input",
      name: "Micro USB",
    });
  });

  it("should_retirer_un_appareil_deja_ajoute_de_la_liste_a_ajouter", () => {
    render(<AudioPanel {...({} as IDockviewPanelProps)} />);
    emit({
      type: "audio_devices",
      inputs: [{ name: "Micro USB", device_id: "dev-1" }],
      outputs: [],
    });
    emit({ type: "audio_sources", items: [source()] });

    // Une source déjà dans le mixeur ne doit plus apparaître comme « à ajouter ».
    expect(screen.queryByText("+ Micro USB")).not.toBeInTheDocument();
  });

  it("should_couper_puis_retablir_une_source", async () => {
    const user = userEvent.setup();
    render(<AudioPanel {...({} as IDockviewPanelProps)} />);
    emit({
      type: "audio_devices",
      inputs: [{ name: "Micro USB", device_id: "dev-1" }],
      outputs: [],
    });
    emit({ type: "audio_sources", items: [source({ muted: false })] });

    const bouton = screen.getByRole("button", { name: "Couper" });
    await user.click(bouton);

    expect(invokeMock).toHaveBeenCalledWith("set_audio_muted", {
      name: "Micro USB",
      muted: true,
    });
  });

  it("should_afficher_l_etat_coupe_quand_la_source_est_muted", () => {
    render(<AudioPanel {...({} as IDockviewPanelProps)} />);
    emit({
      type: "audio_devices",
      inputs: [{ name: "Micro USB", device_id: "dev-1" }],
      outputs: [],
    });
    emit({ type: "audio_sources", items: [source({ muted: true })] });

    const bouton = screen.getByRole("button", { name: "Coupé" });
    expect(bouton).toHaveAttribute("aria-pressed", "true");
  });

  it("should_retirer_une_source_du_mixeur", async () => {
    const user = userEvent.setup();
    render(<AudioPanel {...({} as IDockviewPanelProps)} />);
    emit({
      type: "audio_devices",
      inputs: [{ name: "Micro USB", device_id: "dev-1" }],
      outputs: [],
    });
    emit({ type: "audio_sources", items: [source()] });

    await user.click(
      screen.getByRole("button", { name: "Retirer Micro USB du mixeur" }),
    );

    expect(invokeMock).toHaveBeenCalledWith("remove_audio_source", {
      name: "Micro USB",
    });
  });

  it("should_ouvrir_la_fenetre_de_reglages_au_clic_sur_l_icone_dediee", async () => {
    const user = userEvent.setup();
    render(<AudioPanel {...({} as IDockviewPanelProps)} />);
    emit({
      type: "audio_devices",
      inputs: [{ name: "Micro USB", device_id: "dev-1" }],
      outputs: [],
    });
    emit({ type: "audio_sources", items: [source()] });

    await user.click(
      screen.getByRole("button", { name: "Réglages de Micro USB" }),
    );

    expect(
      screen.getByRole("heading", { name: "Réglages — Micro USB" }),
    ).toBeInTheDocument();
  });

  it("should_afficher_le_volume_de_retour_seulement_quand_le_streamer_l_ecoute", () => {
    render(<AudioPanel {...({} as IDockviewPanelProps)} />);
    emit({
      type: "audio_devices",
      inputs: [{ name: "Micro USB", device_id: "dev-1" }],
      outputs: [],
    });

    emit({
      type: "audio_sources",
      items: [source({ monitoring: "none" })],
    });
    expect(screen.queryByLabelText(/dans mon casque/i)).not.toBeInTheDocument();

    emit({
      type: "audio_sources",
      items: [source({ monitoring: "monitor_only" })],
    });
    expect(screen.getByLabelText(/dans mon casque/i)).toBeInTheDocument();
  });

  it("should_annoncer_une_saturation_sans_repeter_l_alerte_dans_la_fenetre_de_rappel", () => {
    render(<AudioPanel {...({} as IDockviewPanelProps)} />);
    emit({
      type: "audio_devices",
      inputs: [{ name: "Micro USB", device_id: "dev-1" }],
      outputs: [],
    });
    emit({ type: "audio_sources", items: [source()] });

    emit({
      type: "audio_levels",
      levels: [{ name: "Micro USB", magnitude_db: 0 }],
    });
    // getByRole(..., { name }) echoue ici sur un calcul du nom accessible qui ne colle
    // pas au texte reel (verifie : le role existe, le texte affiche est le bon — seule la
    // correspondance nom+role du calculateur d acccessible-name est en cause, pas le
    // composant). On verifie donc le role et le texte separement, avec la meme exigence.
    const alerte = screen.getByRole("alert");
    expect(alerte).toHaveTextContent("Le son sature sur Micro USB");
  });

  it("should_afficher_le_message_d_erreur_envoye_par_le_moteur", () => {
    render(<AudioPanel {...({} as IDockviewPanelProps)} />);

    emit({ type: "error", message: "Le périphérique a disparu" });

    expect(screen.getByText(/Le périphérique a disparu/i)).toBeInTheDocument();
  });

  it("should_desabonner_l_ecoute_du_moteur_au_demontage", async () => {
    const unlisten = vi.fn();
    listenMock.mockImplementation(
      (_event: string, cb: typeof engineListener) => {
        engineListener = cb;
        return Promise.resolve(unlisten);
      },
    );
    const { unmount } = render(<AudioPanel {...({} as IDockviewPanelProps)} />);

    unmount();
    await Promise.resolve(); // laisse le microtask du désabonnement s'exécuter
    expect(unlisten).toHaveBeenCalledTimes(1);
  });
});
