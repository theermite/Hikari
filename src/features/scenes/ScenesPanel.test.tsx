// @vitest-environment jsdom
//
// Filet de non-régression AVANT découpage de ScenesPanel.tsx (850 lignes, au-dessus du
// plafond BLOQUANT de 500 — Quality.md). Même méthode que AudioPanel : les tests avant le
// code, pour découper sans naviguer à l'aveugle sur le plus stateful des panneaux du
// cockpit (rejeu de session, écoute croisée avec le mixeur audio).
//
// Limite honnête : ce filet couvre la liste des scènes, la création, le changement de
// scène, le renommage, la suppression et l'ajout d'une source — pas le détail du rejeu de
// session au démarrage (`restoreSession`), qui mériterait son propre chantier de tests dédié.

import { act, cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { IDockviewPanelProps } from "dockview-react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ScenesPanel } from "./ScenesPanel";
import type { CaptureTarget, EngineMessage, SceneInfo } from "./types";

const invokeMock = vi.hoisted(() => vi.fn().mockResolvedValue(undefined));
vi.mock("@tauri-apps/api/core", () => ({ invoke: invokeMock }));

const dialogOpenMock = vi.hoisted(() => vi.fn());
vi.mock("@tauri-apps/plugin-dialog", () => ({ open: dialogOpenMock }));

let engineListener: ((event: { payload: EngineMessage }) => void) | null = null;
const listenMock = vi.hoisted(() => vi.fn());
vi.mock("@tauri-apps/api/event", () => ({ listen: listenMock }));

// La session (localStorage-like) et la disposition sont lues au montage — neutralisées
// pour ne pas dépendre d'un vrai stockage entre deux tests.
vi.mock("./sessionStore", () => ({}));

function emit(message: EngineMessage) {
  act(() => {
    engineListener?.({ payload: message });
  });
}

function scene(overrides: Partial<SceneInfo> = {}): SceneInfo {
  return {
    name: "main",
    has_camera: false,
    sources: [],
    ...overrides,
  };
}

/** La <li> d une scene precise, trouvee par son NOM accessible.
 *
 * Anciennement : le premier element de liste dont le texte COMMENCE par le nom. Cette
 * forme cassait des qu on ajoutait quoi que ce soit avant le nom — la vignette du
 * 2026-09-05 l a fait tomber. Le nom accessible ne depend pas de l ordre du contenu. */
function sceneRow(name: string) {
  return screen
    .getAllByRole("listitem")
    .find((li) => li.getAttribute("aria-label") === name);
}

function ready(scenes: SceneInfo[], active = scenes[0]?.name ?? "main") {
  emit({ type: "scene_list", scenes, active });
}

beforeEach(() => {
  invokeMock.mockClear();
  dialogOpenMock.mockReset().mockResolvedValue(null);
  engineListener = null;
  listenMock.mockImplementation((_event: string, cb: typeof engineListener) => {
    engineListener = cb;
    return Promise.resolve(() => {});
  });
});

afterEach(() => {
  cleanup();
});

describe("ScenesPanel", () => {
  it("should_afficher_un_message_d_attente_avant_que_le_moteur_reponde", () => {
    render(<ScenesPanel {...({} as IDockviewPanelProps)} />);

    expect(
      screen.getByText(/Ouvre le panneau Aperçu pour gérer les scènes/i),
    ).toBeInTheDocument();
  });

  it("should_lister_les_scenes_recues_du_moteur", () => {
    render(<ScenesPanel {...({} as IDockviewPanelProps)} />);

    ready([scene({ name: "main" }), scene({ name: "brb" })]);

    expect(sceneRow("main")).toBeTruthy();
    expect(sceneRow("brb")).toBeTruthy();
  });

  it("should_marquer_la_scene_active_comme_en_direct", () => {
    render(<ScenesPanel {...({} as IDockviewPanelProps)} />);

    ready([scene({ name: "main" }), scene({ name: "brb" })], "main");

    const ligne = sceneRow("main");
    expect(ligne).toHaveTextContent("● en direct");
    expect(within(ligne as HTMLElement).getByText(/main/)).toBeDisabled();
  });

  it("should_basculer_de_scene_au_clic", async () => {
    const user = userEvent.setup();
    render(<ScenesPanel {...({} as IDockviewPanelProps)} />);
    ready([scene({ name: "main" }), scene({ name: "brb" })], "main");

    await user.click(screen.getByRole("button", { name: "brb" }));

    expect(invokeMock).toHaveBeenCalledWith("switch_scene", { name: "brb" });
  });

  it("should_creer_une_scene_quand_le_nom_n_est_pas_vide", async () => {
    const user = userEvent.setup();
    render(<ScenesPanel {...({} as IDockviewPanelProps)} />);
    ready([scene({ name: "main" })]);

    await user.type(
      screen.getByPlaceholderText("Nom de la nouvelle scène"),
      "intermission",
    );
    await user.click(screen.getByRole("button", { name: "Créer" }));

    expect(invokeMock).toHaveBeenCalledWith("create_scene", {
      name: "intermission",
    });
  });

  it("should_desactiver_le_bouton_creer_quand_le_nom_est_vide", () => {
    render(<ScenesPanel {...({} as IDockviewPanelProps)} />);
    ready([scene({ name: "main" })]);

    expect(screen.getByRole("button", { name: "Créer" })).toBeDisabled();
  });

  it("should_demander_confirmation_avant_de_supprimer_une_scene", async () => {
    const user = userEvent.setup();
    render(<ScenesPanel {...({} as IDockviewPanelProps)} />);
    ready([scene({ name: "main" }), scene({ name: "brb" })]);

    await user.click(screen.getByRole("button", { name: /Supprimer main/ }));

    expect(screen.getByText(/Supprimer « main » \?/)).toBeInTheDocument();
    // Rien n'est encore parti au moteur : la confirmation n'a pas été donnée.
    expect(invokeMock).not.toHaveBeenCalledWith(
      "delete_scene",
      expect.anything(),
    );
  });

  it("should_supprimer_la_scene_apres_confirmation", async () => {
    const user = userEvent.setup();
    render(<ScenesPanel {...({} as IDockviewPanelProps)} />);
    ready([scene({ name: "main" }), scene({ name: "brb" })]);

    await user.click(screen.getByRole("button", { name: /Supprimer main/ }));
    await user.click(screen.getByRole("button", { name: "Supprimer" }));

    expect(invokeMock).toHaveBeenCalledWith("delete_scene", { name: "main" });
  });

  it("should_empecher_de_supprimer_la_derniere_scene", () => {
    render(<ScenesPanel {...({} as IDockviewPanelProps)} />);
    ready([scene({ name: "main" })]);

    expect(
      screen.getByRole("button", { name: /Supprimer main/ }),
    ).toBeDisabled();
  });

  it("should_afficher_le_contenu_d_une_scene_sans_camera", () => {
    render(<ScenesPanel {...({} as IDockviewPanelProps)} />);
    ready([scene({ name: "main", has_camera: false })]);

    expect(screen.getByText("Aucune caméra")).toBeInTheDocument();
  });

  it("should_ouvrir_le_choix_de_source_et_lister_les_cibles_du_moteur", async () => {
    const user = userEvent.setup();
    render(<ScenesPanel {...({} as IDockviewPanelProps)} />);
    ready([scene({ name: "main" })]);

    await user.click(
      screen.getByRole("button", { name: "+ Ajouter une source" }),
    );
    const target: CaptureTarget = { id: "game-1", label: "Dofus 3" };
    emit({
      type: "capture_targets",
      games: [target],
      windows: [],
      monitors: [],
    });

    expect(
      within(screen.getByRole("dialog")).getByText(/Dofus 3/),
    ).toBeInTheDocument();
  });

  it("should_ajouter_une_source_choisie_a_la_scene", async () => {
    const user = userEvent.setup();
    render(<ScenesPanel {...({} as IDockviewPanelProps)} />);
    ready([scene({ name: "main" })]);

    await user.click(
      screen.getByRole("button", { name: "+ Ajouter une source" }),
    );
    emit({
      type: "capture_targets",
      games: [{ id: "game-1", label: "Dofus 3" }],
      windows: [],
      monitors: [],
    });
    await user.click(screen.getByText(/Dofus 3/));

    expect(invokeMock).toHaveBeenCalledWith("add_capture_source", {
      scene: "main",
      kind: "game",
      targetId: "game-1",
      name: "Dofus 3",
    });
  });

  // --- La caméra est une source ordinaire (Jay, 2026-09-06) ------------------------
  //
  // Elle s'ajoutait depuis un panneau à part : deux portes d'entrée pour un même geste.
  // Ces tests fixent la porte unique.

  it("should_proposer_les_cameras_de_la_machine_parmi_les_sources", async () => {
    const user = userEvent.setup();
    invokeMock.mockImplementation((cmd: string) =>
      cmd === "list_cameras"
        ? Promise.resolve([{ name: "Logitech StreamCam", device_id: "cam-1" }])
        : Promise.resolve(undefined),
    );
    render(<ScenesPanel {...({} as IDockviewPanelProps)} />);
    ready([scene({ name: "main" })]);

    await user.click(
      screen.getByRole("button", { name: "+ Ajouter une source" }),
    );
    emit({ type: "capture_targets", games: [], windows: [], monitors: [] });
    await user.click(screen.getByRole("button", { name: "Une caméra" }));

    expect(
      await within(screen.getByRole("dialog")).findByText(/Logitech StreamCam/),
    ).toBeInTheDocument();
  });

  it("should_poser_la_camera_par_sa_propre_commande_jamais_comme_une_capture", async () => {
    // Une caméra est UN appareil partagé entre les scènes : `add_capture_source`
    // l'ouvrirait une seconde fois. Le moteur a sa commande pour ça.
    const user = userEvent.setup();
    invokeMock.mockImplementation((cmd: string) =>
      cmd === "list_cameras"
        ? Promise.resolve([{ name: "Logitech StreamCam", device_id: "cam-1" }])
        : Promise.resolve(undefined),
    );
    render(<ScenesPanel {...({} as IDockviewPanelProps)} />);
    ready([scene({ name: "main" })]);

    await user.click(
      screen.getByRole("button", { name: "+ Ajouter une source" }),
    );
    emit({ type: "capture_targets", games: [], windows: [], monitors: [] });
    await user.click(screen.getByRole("button", { name: "Une caméra" }));
    await user.click(await screen.findByText(/Logitech StreamCam/));

    expect(invokeMock).toHaveBeenCalledWith("add_camera_source", {
      deviceId: "cam-1",
      scene: "main",
    });
    expect(invokeMock).not.toHaveBeenCalledWith(
      "add_capture_source",
      expect.anything(),
    );
  });

  it("should_ne_pas_reproposer_une_camera_deja_posee_dans_cette_scene", async () => {
    // La rajouter n'ouvrirait rien de neuf, et le moteur la refuserait — un refus qu'on
    // peut éviter de provoquer vaut mieux qu'un refus bien affiché.
    const user = userEvent.setup();
    invokeMock.mockImplementation((cmd: string) =>
      cmd === "list_cameras"
        ? Promise.resolve([{ name: "Logitech StreamCam", device_id: "cam-1" }])
        : Promise.resolve(undefined),
    );
    render(<ScenesPanel {...({} as IDockviewPanelProps)} />);
    ready([
      scene({
        name: "main",
        has_camera: true,
        sources: [
          {
            name: "Logitech StreamCam",
            kind: "dshow_input",
            source_kind: "camera",
            target_id: "cam-1",
            x: 0,
            y: 0,
            scale_percent: 100,
            locked: false,
            background_removal: false,
            circle_mask: false,
          },
        ],
      }),
    ]);

    await user.click(
      screen.getByRole("button", { name: "+ Ajouter une source" }),
    );
    emit({ type: "capture_targets", games: [], windows: [], monitors: [] });
    await user.click(screen.getByRole("button", { name: "Une caméra" }));

    expect(
      within(screen.getByRole("dialog")).queryByRole("button", {
        name: /Logitech StreamCam/,
      }),
    ).not.toBeInTheDocument();
  });

  it("should_ouvrir_les_reglages_d_une_camera_depuis_sa_ligne_de_source", async () => {
    // LA régression du 2026-09-06 : les réglages de caméra étaient inatteignables. Ils
    // vivent désormais au même endroit que la caméra elle-même — sa ligne dans la scène.
    const user = userEvent.setup();
    render(<ScenesPanel {...({} as IDockviewPanelProps)} />);
    ready([
      scene({
        name: "main",
        has_camera: true,
        sources: [
          {
            name: "Logitech StreamCam",
            kind: "dshow_input",
            source_kind: "camera",
            target_id: "cam-1",
            x: 0,
            y: 0,
            scale_percent: 100,
            locked: false,
            background_removal: false,
            circle_mask: false,
          },
        ],
      }),
    ]);

    await user.click(
      screen.getByRole("button", { name: /Réglages de Logitech StreamCam/ }),
    );

    expect(
      within(screen.getByRole("dialog")).getByRole("button", {
        name: /fond IA/i,
      }),
    ).toBeInTheDocument();
  });

  it("should_appliquer_le_filtre_a_cette_camera_dans_cette_scene", async () => {
    // Les filtres appartiennent à la caméra ET à la scène : deux caméras d'une même scène
    // peuvent avoir deux allures, et la même caméra deux allures selon la scène.
    const user = userEvent.setup();
    render(<ScenesPanel {...({} as IDockviewPanelProps)} />);
    ready([
      scene({
        name: "main",
        has_camera: true,
        sources: [
          {
            name: "Logitech StreamCam",
            kind: "dshow_input",
            source_kind: "camera",
            target_id: "cam-1",
            x: 0,
            y: 0,
            scale_percent: 100,
            locked: false,
            background_removal: false,
            circle_mask: false,
          },
        ],
      }),
    ]);

    await user.click(
      screen.getByRole("button", { name: /Réglages de Logitech StreamCam/ }),
    );
    await user.click(
      within(screen.getByRole("dialog")).getByRole("button", {
        name: /fond IA/i,
      }),
    );

    expect(invokeMock).toHaveBeenCalledWith("set_background_removal", {
      deviceId: "cam-1",
      scene: "main",
      enabled: true,
    });
  });

  it("should_annoncer_les_reglages_a_venir_sur_une_source_ordinaire", async () => {
    // Décision du 2026-09-05 : dessiner le squelette complet et le marquer « à venir »,
    // plutôt que de laisser un trou. Un bouton absent ferait croire à un oubli.
    render(<ScenesPanel {...({} as IDockviewPanelProps)} />);
    ready([
      scene({
        name: "main",
        sources: [
          {
            name: "Dofus 3",
            kind: "game_capture",
            source_kind: "game",
            target_id: "game-1",
            x: 0,
            y: 0,
            scale_percent: 100,
            locked: false,
            background_removal: false,
            circle_mask: false,
          },
        ],
      }),
    ]);

    const reglages = screen.getByLabelText(/Réglages de Dofus 3/);

    // Marqué « à venir » par le seul composant qui a le droit de le dire.
    expect(reglages.closest('[aria-disabled="true"]')).not.toBeNull();
  });

  // Le refus du moteur appartient au bandeau du cockpit depuis le 2026-09-06
  // (`EngineErrorBanner`) : il arrive de façon asynchrone, souvent pendant qu'un autre
  // panneau est au premier plan. L'afficher ici EN PLUS le montrerait deux fois quand ce
  // panneau est ouvert, et pas du tout quand il ne l'est pas.
  it("should_laisser_le_bandeau_du_cockpit_porter_le_refus_du_moteur", () => {
    render(<ScenesPanel {...({} as IDockviewPanelProps)} />);

    emit({ type: "error", message: "La scène existe déjà" });

    expect(screen.queryByText(/La scène existe déjà/i)).not.toBeInTheDocument();
  });

  it("should_desabonner_l_ecoute_du_moteur_au_demontage", async () => {
    const unlisten = vi.fn();
    listenMock.mockImplementation(
      (_event: string, cb: typeof engineListener) => {
        engineListener = cb;
        return Promise.resolve(unlisten);
      },
    );
    const { unmount } = render(
      <ScenesPanel {...({} as IDockviewPanelProps)} />,
    );

    unmount();
    await Promise.resolve();
    expect(unlisten).toHaveBeenCalledTimes(1);
  });
});
