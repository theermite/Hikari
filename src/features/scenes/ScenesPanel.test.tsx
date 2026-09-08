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

// Le stockage de session est simulé pour pouvoir OBSERVER ce qui y est écrit — c'est le
// seul moyen de prouver qu'une session n'est pas détruite.
const saveSessionMock = vi.hoisted(() => vi.fn().mockResolvedValue(undefined));
const loadSessionMock = vi.hoisted(() => vi.fn());
vi.mock("./sceneLayout", async (importOriginal) => {
  const actual = await importOriginal<typeof import("./sceneLayout")>();
  return {
    ...actual,
    saveSession: saveSessionMock,
    loadSession: loadSessionMock,
    saveSceneLayout: vi.fn().mockResolvedValue(undefined),
    loadSceneLayout: vi.fn().mockResolvedValue(actual.EMPTY_LAYOUT),
  };
});

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

    // 300 = le défaut affiché (`TRANSITION_DURATIONS_MS[1]`, « Fondu 0,3 s »).
    expect(invokeMock).toHaveBeenCalledWith("switch_scene", {
      name: "brb",
      durationMs: 300,
    });
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
            visible: true,
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

  it("should_ouvrir_les_reglages_d_une_camera_dans_une_fenetre_separee", async () => {
    // Jay, 2026-09-07 : « c'est absolument contre-intuitif [...] c'est une fenêtre qui
    // apparaît pour que l'on puisse régler », comme dans OBS. Le panneau replié SOUS la
    // ligne (régression du 2026-09-06, corrigée alors) est remplacé par une vraie fenêtre
    // native — le contenu (`CameraControls`) vit désormais dans `SettingsWindow.tsx`.
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
            visible: true,
          },
        ],
      }),
    ]);

    await user.click(
      screen.getByRole("button", { name: /Réglages de Logitech StreamCam/ }),
    );

    expect(invokeMock).toHaveBeenCalledWith("open_settings_window", {
      kind: "camera",
      scene: "main",
      name: "Logitech StreamCam",
      initial: null,
    });
    // Rien ne se déplie plus dans la ligne : le contenu vit dans la fenêtre séparée.
    expect(
      screen.queryByRole("button", { name: /fond IA/i }),
    ).not.toBeInTheDocument();
  });

  it("should_ouvrir_ou_focaliser_la_meme_fenetre_a_chaque_clic", async () => {
    // Plus de repli local à fermer/rouvrir : chaque clic redemande l'ouverture, et c'est
    // la commande côté Rust qui décide de créer une fenêtre ou de focaliser celle qui
    // existe déjà pour cette source (voir `settings_window.rs`, `window_label`).
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
            visible: true,
          },
        ],
      }),
    ]);
    const bouton = screen.getByRole("button", {
      name: /Réglages de Logitech StreamCam/,
    });

    await user.click(bouton);
    await user.click(bouton);

    const appels = invokeMock.mock.calls.filter(
      ([nom]) => nom === "open_settings_window",
    );
    expect(appels).toHaveLength(2);
    expect(appels[0]).toEqual(appels[1]);
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
            visible: true,
          },
        ],
      }),
    ]);

    const reglages = screen.getByLabelText(/Réglages de Dofus 3/);

    // Marqué « à venir » par le seul composant qui a le droit de le dire.
    expect(reglages.closest('[aria-disabled="true"]')).not.toBeNull();
  });

  // --- L'œil montrer/cacher (maquette, 2026-09-06) -----------------------------------
  //
  // Le geste du direct : masquer une source le temps d'une manipulation, puis la
  // remontrer. Distinct du retrait, qui est une décision.

  it("should_cacher_une_source_visible_quand_on_clique_l_oeil", async () => {
    const user = userEvent.setup();
    render(<ScenesPanel {...({} as IDockviewPanelProps)} />);
    ready([
      scene({
        name: "main",
        sources: [
          {
            name: "Overlay LoL",
            kind: "image_source",
            source_kind: "image",
            target_id: "D:/overlay.png",
            x: 0,
            y: 0,
            scale_percent: 100,
            locked: false,
            background_removal: false,
            circle_mask: false,
            visible: true,
          },
        ],
      }),
    ]);

    await user.click(
      screen.getByRole("button", { name: /Cacher Overlay LoL/ }),
    );

    expect(invokeMock).toHaveBeenCalledWith("set_source_visible", {
      scene: "main",
      name: "Overlay LoL",
      visible: false,
    });
  });

  it("should_remontrer_une_source_cachee", async () => {
    const user = userEvent.setup();
    render(<ScenesPanel {...({} as IDockviewPanelProps)} />);
    ready([
      scene({
        name: "main",
        sources: [
          {
            name: "Overlay LoL",
            kind: "image_source",
            source_kind: "image",
            target_id: "D:/overlay.png",
            x: 0,
            y: 0,
            scale_percent: 100,
            locked: false,
            background_removal: false,
            circle_mask: false,
            visible: false,
          },
        ],
      }),
    ]);

    await user.click(
      screen.getByRole("button", { name: /Montrer Overlay LoL/ }),
    );

    expect(invokeMock).toHaveBeenCalledWith("set_source_visible", {
      scene: "main",
      name: "Overlay LoL",
      visible: true,
    });
  });

  it("should_dire_a_un_lecteur_d_ecran_si_la_source_est_montree", async () => {
    // Un pictogramme d'œil barré ne se lit pas. L'état doit être porté par le bouton.
    render(<ScenesPanel {...({} as IDockviewPanelProps)} />);
    ready([
      scene({
        name: "main",
        sources: [
          {
            name: "Overlay LoL",
            kind: "image_source",
            source_kind: "image",
            target_id: "D:/overlay.png",
            x: 0,
            y: 0,
            scale_percent: 100,
            locked: false,
            background_removal: false,
            circle_mask: false,
            visible: false,
          },
        ],
      }),
    ]);

    expect(
      screen.getByRole("button", { name: /Montrer Overlay LoL/ }),
    ).toHaveAttribute("aria-pressed", "false");
  });

  // --- Ce que la maquette dessine et qui n'est pas encore branché ---------------------
  //
  // Décision de Jay du 2026-09-05 : dessiner le squelette complet et le marquer « à
  // venir ». On sait ce qui arrive, on voit à quoi ça ressemblera, et le squelette tient
  // au lieu d'être rapiécé brique après brique.

  it("should_dessiner_la_ligne_de_transition_de_la_maquette", () => {
    render(<ScenesPanel {...({} as IDockviewPanelProps)} />);
    ready([scene({ name: "main" })]);

    expect(screen.getByText(/Transition/)).toBeInTheDocument();
  });

  it("should_changer_la_scene_avec_la_duree_choisie_dans_le_selecteur", async () => {
    const user = userEvent.setup();
    render(<ScenesPanel {...({} as IDockviewPanelProps)} />);
    ready([scene({ name: "main" }), scene({ name: "brb" })], "main");

    await user.selectOptions(screen.getByRole("combobox"), "0");
    await user.click(screen.getByRole("button", { name: "brb" }));

    expect(invokeMock).toHaveBeenCalledWith("switch_scene", {
      name: "brb",
      durationMs: 0,
    });
  });

  it("should_dessiner_les_collections_de_scenes", () => {
    // La maquette groupe les scènes par collection (LoL, Interview, Pause). Rien ne les
    // porte encore côté moteur.
    render(<ScenesPanel {...({} as IDockviewPanelProps)} />);
    ready([scene({ name: "main" })]);

    const collections = screen.getByLabelText(/Collections de scènes/);

    expect(collections.closest('[aria-disabled="true"]')).not.toBeNull();
  });

  it("should_ne_rien_dessiner_de_tout_ca_tant_que_le_moteur_se_tait", () => {
    // Un squelette annoncé au-dessus d'une liste vide, avant même de savoir s'il y a des
    // scènes, ferait un panneau qui parle de ce qu'il n'a pas.
    render(<ScenesPanel {...({} as IDockviewPanelProps)} />);

    expect(screen.queryByText(/Transition/)).not.toBeInTheDocument();
  });

  it("should_demander_le_texte_a_ecrire_plutot_qu_une_cible", async () => {
    // Le contenu d'une source texte vient de l'utilisateur, pas de la machine : ni liste
    // de cibles, ni sélecteur de fichier. Un champ, et c'est tout.
    const user = userEvent.setup();
    render(<ScenesPanel {...({} as IDockviewPanelProps)} />);
    ready([scene({ name: "main" })]);

    await user.click(
      screen.getByRole("button", { name: "+ Ajouter une source" }),
    );
    emit({ type: "capture_targets", games: [], windows: [], monitors: [] });
    await user.click(screen.getByRole("button", { name: "Du texte" }));

    expect(
      screen.getByRole("textbox", { name: /texte à afficher/i }),
    ).toBeInTheDocument();
  });

  it("should_poser_le_texte_ecrit_dans_la_scene", async () => {
    const user = userEvent.setup();
    render(<ScenesPanel {...({} as IDockviewPanelProps)} />);
    ready([scene({ name: "main" })]);

    await user.click(
      screen.getByRole("button", { name: "+ Ajouter une source" }),
    );
    emit({ type: "capture_targets", games: [], windows: [], monitors: [] });
    await user.click(screen.getByRole("button", { name: "Du texte" }));
    await user.type(
      screen.getByRole("textbox", { name: /texte à afficher/i }),
      "Bientôt de retour",
    );
    await user.click(screen.getByRole("button", { name: /Ajouter le texte/ }));

    expect(invokeMock).toHaveBeenCalledWith("add_capture_source", {
      scene: "main",
      kind: "text",
      targetId: "Bientôt de retour",
      name: "Bientôt de retour",
    });
  });

  it("should_refuser_d_ajouter_un_texte_vide", async () => {
    // Une source texte vide est un rectangle invisible que l'utilisateur ne retrouvera
    // pas — il la cherchera dans sa scène sans jamais la voir.
    const user = userEvent.setup();
    render(<ScenesPanel {...({} as IDockviewPanelProps)} />);
    ready([scene({ name: "main" })]);

    await user.click(
      screen.getByRole("button", { name: "+ Ajouter une source" }),
    );
    emit({ type: "capture_targets", games: [], windows: [], monitors: [] });
    await user.click(screen.getByRole("button", { name: "Du texte" }));

    expect(
      screen.getByRole("button", { name: /Ajouter le texte/ }),
    ).toBeDisabled();
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
    // Deux abonnements distincts vivent ici depuis la fenêtre de réglages séparée
    // (2026-09-07) : l'écoute des messages du moteur, et celle des changements
    // d'apparence de texte qu'une fenêtre séparée annonce (`useTextSettings`). Les deux
    // doivent se désabonner au démontage.
    expect(unlisten).toHaveBeenCalledTimes(2);
  });

  it("should_never_overwrite_the_saved_session_when_a_fresh_engine_reports_its_naked_state", async () => {
    // Défaut vécu le 2026-09-07, et il a DÉTRUIT le travail de Jay : relancer le moteur en
    // cours de session le fait repartir avec la seule scène « main ». L'écran ne rejouait
    // la session qu'UNE fois par ouverture de l'application ; au second inventaire il
    // prenait donc cet état nu pour la vérité et l'écrivait par-dessus les vraies scènes.
    //
    // La garde d'origine demandait « a-t-on déjà rejoué ? ». La bonne question est « ce
    // moteur est-il neuf ? » — sinon un moteur qui redémarrerait seul détruirait pareil.
    loadSessionMock.mockResolvedValue({
      active: "main",
      audio: [],
      scenes: [
        { name: "main", sources: [], cameras: [] },
        { name: "Dofus", sources: [], cameras: [] },
      ],
    });

    render(<ScenesPanel {...({} as IDockviewPanelProps)} />);
    emit({ type: "ready" });
    emit({
      type: "scene_list",
      active: "main",
      scenes: [scene({ name: "main" }), scene({ name: "Dofus" })],
    });
    // Le rejeu doit AVOIR FINI avant la suite : sans cette attente, le drapeau « rejeu en
    // cours » bloque encore la sauvegarde et le test passerait pour une mauvaise raison —
    // exactement le faux vert constaté en l'écrivant.
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });
    saveSessionMock.mockClear();

    // Le moteur redémarre : nouveau signal de démarrage, puis un inventaire nu.
    emit({ type: "ready" });
    emit({
      type: "scene_list",
      active: "main",
      scenes: [scene({ name: "main" })],
    });
    await act(async () => {
      await Promise.resolve();
    });

    const destructive = saveSessionMock.mock.calls.filter(
      ([doc]) => (doc?.scenes?.length ?? 0) < 2,
    );
    expect(destructive).toHaveLength(0);
  });

  it("should_never_overwrite_the_saved_audio_when_a_fresh_engine_reports_no_device", async () => {
    // Second versant du même défaut, et Jay l'a perdu aussi le 2026-09-07 : ses appareils
    // audio. Un moteur neuf annonce zéro appareil AVANT que le rejeu ne commence ; la garde
    // ne regardait que « un rejeu est-il en cours ? », donc cette liste vide passait et
    // écrasait le mixeur entier.
    loadSessionMock.mockResolvedValue({
      active: "main",
      audio: [
        { name: "Micro", kind: "input", muted: false, monitoring: false },
      ],
      scenes: [{ name: "main", sources: [], cameras: [] }],
    });

    render(<ScenesPanel {...({} as IDockviewPanelProps)} />);
    emit({ type: "ready" });
    emit({
      type: "scene_list",
      active: "main",
      scenes: [scene({ name: "main" })],
    });
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });
    saveSessionMock.mockClear();

    // Le moteur redémarre et annonce son mixeur vide avant tout rejeu.
    emit({ type: "ready" });
    emit({ type: "audio_sources", items: [] } as unknown as EngineMessage);
    await act(async () => {
      await Promise.resolve();
    });

    const destructive = saveSessionMock.mock.calls.filter(
      ([doc]) => (doc?.audio?.length ?? 0) === 0,
    );
    expect(destructive).toHaveLength(0);
  });

  it("should_never_save_a_partial_replay_while_a_failed_step_is_still_retrying", async () => {
    // Troisième versant du même défaut (2026-09-08), vécu en direct : une SEULE commande du
    // rejeu en échec (appareil audio ou caméra momentanément indisponible — vu ce soir dans
    // les journaux, instabilité WASAPI) arrêtait tout le reste, et l'inventaire tronqué qui
    // restait devenait la vérité enregistrée au prochain message du moteur.
    loadSessionMock.mockResolvedValue({
      active: "main",
      audio: [],
      scenes: [
        { name: "main", sources: [], cameras: [] },
        { name: "Dofus", sources: [], cameras: [] },
      ],
    });
    let createSceneCalls = 0;
    invokeMock.mockImplementation((cmd: string) => {
      if (cmd === "create_scene") {
        createSceneCalls += 1;
        // Échoue au premier essai (l'appareil), réussit au second (le retenter suffit).
        return createSceneCalls === 1
          ? Promise.reject(new Error("appareil momentanément indisponible"))
          : Promise.resolve(undefined);
      }
      return Promise.resolve(undefined);
    });

    render(<ScenesPanel {...({} as IDockviewPanelProps)} />);
    emit({ type: "ready" });
    emit({
      type: "scene_list",
      active: "main",
      scenes: [scene({ name: "main" })],
    });
    // Le premier essai échoue à `create_scene` : `restoreOk` doit rester FAUX pendant
    // toute cette fenêtre, avant même que le second essai n'ait eu la chance de tourner.
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });
    const destructiveWhileRetrying = saveSessionMock.mock.calls.filter(
      ([doc]) => (doc?.scenes?.length ?? 0) < 2,
    );
    expect(destructiveWhileRetrying).toHaveLength(0);

    // Le second essai tourne à son tour et réussit — la session complète est maintenant
    // rejouée, plus rien ne doit avoir été enregistré de tronqué entre-temps.
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(createSceneCalls).toBe(2);
    const destructive = saveSessionMock.mock.calls.filter(
      ([doc]) => (doc?.scenes?.length ?? 0) < 2,
    );
    expect(destructive).toHaveLength(0);
  });

  it("should_surface_an_error_when_the_replay_fails_twice_in_a_row", async () => {
    loadSessionMock.mockResolvedValue({
      active: "main",
      audio: [],
      scenes: [
        { name: "main", sources: [], cameras: [] },
        { name: "Dofus", sources: [], cameras: [] },
      ],
    });
    invokeMock.mockImplementation((cmd: string) =>
      cmd === "create_scene"
        ? Promise.reject(new Error("appareil indisponible"))
        : Promise.resolve(undefined),
    );

    render(<ScenesPanel {...({} as IDockviewPanelProps)} />);
    emit({ type: "ready" });
    emit({
      type: "scene_list",
      active: "main",
      scenes: [scene({ name: "main" })],
    });
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
      await Promise.resolve();
      await Promise.resolve();
    });

    // Jamais avalée : Jay doit voir que son cadrage n'a peut-être pas été retrouvé plutôt
    // que de le découvrir en direct.
    expect(screen.getByText(/2 essais/)).toBeInTheDocument();
  });

  it("should_never_save_the_dead_engine_replay_when_the_engine_restarts_mid_replay", async () => {
    // Défaut trouvé en relecture indépendante (2026-09-08) : un moteur qui redémarre
    // PENDANT un rejeu voyait son propre rejeu jeté (`replaying` restait vrai côté ancien
    // rejeu), et c'était l'ANCIEN rejeu — celui du moteur mort — qui finissait par écrire
    // `restoreOk = true` et sauvegarder l'inventaire nu du NOUVEAU moteur par-dessus la
    // vraie session.
    loadSessionMock.mockResolvedValue({
      active: "main",
      audio: [],
      scenes: [
        { name: "main", sources: [], cameras: [] },
        { name: "Dofus", sources: [], cameras: [] },
      ],
    });
    const pending: { release: (() => void) | null } = { release: null };
    let createSceneCalls = 0;
    invokeMock.mockImplementation((cmd: string) => {
      if (cmd === "create_scene") {
        createSceneCalls += 1;
        if (createSceneCalls === 1) {
          // Le PREMIER essai ne se termine jamais tout seul — c'est le moteur qui
          // redémarre pendant qu'il attend, exactement le scénario du défaut.
          return new Promise<void>((resolve) => {
            pending.release = resolve;
          });
        }
      }
      return Promise.resolve(undefined);
    });

    render(<ScenesPanel {...({} as IDockviewPanelProps)} />);
    emit({ type: "ready" });
    emit({
      type: "scene_list",
      active: "main",
      scenes: [scene({ name: "main" })],
    });
    await act(async () => {
      await Promise.resolve();
    });
    expect(createSceneCalls).toBe(1);

    // Le moteur redémarre EN PLEIN MILIEU du premier rejeu : nouveau signal de démarrage,
    // puis un inventaire nu — le second rejeu qu'il déclenche ne peut pas encore tourner
    // (`replaying` est toujours vrai pour le premier).
    emit({ type: "ready" });
    emit({
      type: "scene_list",
      active: "main",
      scenes: [scene({ name: "main" })],
    });
    await act(async () => {
      await Promise.resolve();
    });

    // Le premier essai, mort, se termine ENFIN — sa réussite ne doit RIEN écrire pour le
    // moteur actuel.
    pending.release?.();
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
      await Promise.resolve();
      await Promise.resolve();
      await Promise.resolve();
    });

    // Le relais a dû relancer un vrai second rejeu pour le bon moteur.
    expect(createSceneCalls).toBe(2);
    const destructive = saveSessionMock.mock.calls.filter(
      ([doc]) => (doc?.scenes?.length ?? 0) < 2,
    );
    expect(destructive).toHaveLength(0);
  });
});
