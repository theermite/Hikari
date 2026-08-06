// Panneau Scènes (multi-scène, étape 3) — la liste dédiée : créer, basculer, renommer,
// réordonner, supprimer, et voir d'un coup d'œil ce que chaque scène contient.
//
// Partage des rôles : le MOTEUR détient l'existence des scènes et leur contenu (caméra,
// filtres) ; l'APPLICATION détient la présentation (étiquette lisible, ordre d'affichage,
// voir `sceneLayout.ts` pour le pourquoi). Une scène n'est donc jamais renommée côté
// moteur — son identifiant y reste fixe à vie.

import { listen } from "@tauri-apps/api/event";
import { open } from "@tauri-apps/plugin-dialog";
import type { IDockviewPanelProps } from "dockview-react";
import { useEffect, useRef, useState } from "react";
import { Modal } from "../../components/Modal";
import {
  addAudioSource,
  setAudioMonitoring,
  setAudioMuted,
  setAudioVolume,
  setMonitorVolume,
  setNoiseSettings,
} from "../audio/api";
import type { AudioEngineMessage, AudioSourceInfo } from "../audio/types";
import {
  addCameraSource,
  setBackgroundRemoval,
  setCircleMask,
} from "../camera/api";
import {
  addCaptureSource,
  createScene,
  deleteScene,
  listCaptureTargets,
  removeSource,
  reorderSource,
  setSourceTransform,
  switchScene,
} from "./api";
import {
  EMPTY_LAYOUT,
  labelFor,
  loadSceneLayout,
  loadSession,
  moveScene,
  orderScenes,
  type SceneLayout,
  saveSceneLayout,
  saveSession,
  validateLabel,
} from "./sceneLayout";
import { buildReplay, toSession } from "./session";
import {
  dedupeTargets,
  FILE_FILTERS,
  nameFromPath,
  SOURCE_FAMILIES,
  searchAll,
} from "./sourcePicker";
import type {
  CaptureTarget,
  EngineMessage,
  SceneInfo,
  SourceKind,
  SourceOrder,
} from "./types";

type State =
  | { status: "idle" }
  | { status: "ready"; scenes: SceneInfo[]; active: string };

const LABEL_ERRORS = {
  empty: "Le nom ne peut pas être vide.",
  duplicate: "Une autre scène porte déjà ce nom.",
} as const;

/** Un pictogramme par famille de source, pour reconnaître le contenu d'une scène d'un coup
 * d'œil. Clé = identifiant libobs, jamais un nom inventé côté écran. */
const SOURCE_ICON: Record<string, string> = {
  game_capture: "🎮",
  window_capture: "🪟",
  monitor_capture: "🖥️",
  dshow_input: "🎥",
};

/** Le pictogramme d'un résultat de recherche vient de sa famille — un résultat global mêle
 * les familles, il faut donc dire de laquelle il sort. */
const KIND_TO_LIBOBS: Record<string, string> = {
  game: "game_capture",
  window: "window_capture",
  monitor: "monitor_capture",
};

interface CaptureTargets {
  games: CaptureTarget[];
  windows: CaptureTarget[];
  monitors: CaptureTarget[];
}

/** Ce que chaque famille vivante propose. Les familles de fichier n'ont pas de liste : on y
 * ouvre le sélecteur du système. */
function targetsFor(
  kind: SourceKind,
  targets: CaptureTargets,
): CaptureTarget[] {
  if (kind === "game") return targets.games;
  if (kind === "window") return targets.windows;
  if (kind === "monitor") return targets.monitors;
  return [];
}

export function ScenesPanel(_props: IDockviewPanelProps) {
  const [state, setState] = useState<State>({ status: "idle" });
  const [layout, setLayout] = useState<SceneLayout>(EMPTY_LAYOUT);
  const [newName, setNewName] = useState("");
  const [createError, setCreateError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [renaming, setRenaming] = useState<string | null>(null);
  const [draftLabel, setDraftLabel] = useState("");
  const [labelError, setLabelError] = useState<string | null>(null);
  const [confirmingDelete, setConfirmingDelete] = useState<string | null>(null);
  const [addingTo, setAddingTo] = useState<string | null>(null);
  const [targets, setTargets] = useState<CaptureTargets | null>(null);
  const [targetsError, setTargetsError] = useState<string | null>(null);
  const [chosenFamily, setFamily] = useState<SourceKind>("game");
  const [search, setSearch] = useState("");
  const chosenIsFile =
    SOURCE_FAMILIES.find((f) => f.kind === chosenFamily)?.isFile ?? false;
  const renameInput = useRef<HTMLInputElement>(null);
  const searchInput = useRef<HTMLInputElement>(null);
  /** Vrai pendant le rejeu de la session — empêche de réécrire par-dessus ce qu'on restaure. */
  const replaying = useRef(false);
  /** Vrai une fois le rejeu lancé. Tant qu'il est faux, on ne SAUVEGARDE pas : l'état nu du
   * moteur au démarrage écraserait la session qu'on s'apprête justement à lui rendre. */
  const restored = useRef(false);
  /** L'état vu par le rejeu. Une référence et non l'état React : le rejeu démarre depuis une
   * fonction de rappel qui a capturé un état déjà périmé. */
  const stateRef = useRef<SceneInfo[]>([]);
  /** Le mixeur vu par la mémoire. Il vit dans un autre panneau, mais la session est UNE
   * chose : la couper en deux fichiers ferait deux états à garder cohérents. */
  const audioRef = useRef<AudioSourceInfo[]>([]);
  /** La scène en direct, pour que l'écoute du mixeur sache quoi retenir sans dépendre d'un
   * état React déjà périmé au moment où elle s'exécute. */
  const activeRef = useRef("main");

  useEffect(() => {
    /** Rend au moteur la session d'avant : il repart vierge à chaque lancement.
     *
     * Définie DANS l'effet, et non au-dessus : elle n'est appelée que par l'écoute qui vit
     * ici, et une fonction déclarée dehors serait recréée à chaque rendu — l'écoute devrait
     * alors se réabonner sans cesse, ou mentir sur ce dont elle dépend.
     *
     * Les étapes sont jouées EN SÉRIE et non en parallèle : chacune dépend de la précédente
     * (on ne remplit pas une scène qui n'existe pas encore), et le moteur les traite dans
     * l'ordre où elles arrivent. */
    const restoreSession = async () => {
      if (replaying.current) return;
      replaying.current = true;
      try {
        const saved = await loadSession();
        const steps = buildReplay(saved, stateRef.current);
        for (const step of steps) {
          if (step.do === "createScene") await createScene(step.scene);
          if (step.do === "addSource") {
            await addCaptureSource(
              step.scene,
              step.kind,
              step.targetId,
              step.name,
            );
          }
          if (step.do === "transform") {
            await setSourceTransform(
              step.scene,
              step.name,
              step.x,
              step.y,
              step.scalePercent,
            );
          }
          if (step.do === "addCamera") {
            await addCameraSource(step.deviceId, step.scene);
          }
          if (step.do === "cameraFilters") {
            await setBackgroundRemoval(step.scene, step.background);
            await setCircleMask(step.scene, step.circle);
          }
          if (step.do === "addAudio") {
            const a = step.audio;
            await addAudioSource(a.deviceId, a.kind, a.name);
            await setAudioVolume(a.name, a.volumePercent);
            await setMonitorVolume(a.name, a.monitorVolumePercent);
            await setAudioMonitoring(a.name, a.monitoring);
            await setAudioMuted(a.name, a.muted);
            if (a.kind === "input") {
              await setNoiseSettings(
                a.name,
                a.noiseSuppression,
                a.noiseMethod,
                a.noiseLevelDb,
              );
            }
          }
          if (step.do === "switchScene") await switchScene(step.scene);
        }
      } catch (error: unknown) {
        // Une session qu'on ne peut pas rendre est signalée, jamais avalée : l'utilisateur
        // doit savoir que son cadrage n'a pas été retrouvé plutôt que de le découvrir en direct.
        setActionError(`Session non restaurée : ${String(error)}`);
      } finally {
        replaying.current = false;
      }
    };

    const unlisten = listen<EngineMessage>("engine-message", (event) => {
      const msg = event.payload;
      if (msg.type === "scene_list" && msg.scenes && msg.active) {
        setState({ status: "ready", scenes: msg.scenes, active: msg.active });
        stateRef.current = msg.scenes;
        activeRef.current = msg.active;
        // Le rejeu part d'ICI, au premier inventaire reçu, et non du signal de démarrage :
        // il calcule ce qui MANQUE au moteur, donc il lui faut d'abord savoir ce que le
        // moteur a. Lancé trop tôt il croyait le moteur vide et redemandait tout, ce qui
        // affichait « Monitor Capture existe déjà » à chaque lancement (Jay, 2026-08-06).
        //
        // Recevoir un inventaire suffit — inutile d'attendre en plus le signal de démarrage,
        // qu'une page rechargée en cours de session a déjà manqué : le rejeu resterait alors
        // en attente pour toujours, et avec lui la sauvegarde.
        if (!restored.current) {
          restored.current = true;
          restoreSession();
          return;
        }
        // Retenu à CHAQUE changement plutôt qu'à la fermeture : une app fermée brutalement
        // ne sauvegarde rien, et c'est précisément le moment où l'on perd le plus.
        // Jamais AVANT d'avoir rejoué : la session d'avant serait écrasée par l'état nu du
        // moteur au démarrage. Ni PENDANT, où l'état est à moitié reconstruit.
        if (restored.current && !replaying.current) {
          saveSession(
            toSession(msg.scenes, msg.active, audioRef.current),
          ).catch(() => undefined);
        }
      }
      // Le mixeur change dans un autre panneau : on l'écoute ici parce que la session est
      // UNE chose, et qu'un seul endroit doit décider de ce qu'on retient.
      const audioMsg = msg as AudioEngineMessage;
      if (audioMsg.type === "audio_sources" && audioMsg.items) {
        audioRef.current = audioMsg.items;
        if (!replaying.current && stateRef.current.length > 0) {
          saveSession(
            toSession(stateRef.current, activeRef.current, audioMsg.items),
          ).catch(() => undefined);
        }
      }
      // Le moteur refuse lui-même la suppression interdite : on affiche SA raison plutôt
      // que d'inventer un message côté écran.
      // Le moteur vient de démarrer : c'est le seul moment où il PEUT répondre. Sans ce
      // rattrapage, ouvrir l'Aperçu après la fenêtre d'ajout laisserait celle-ci vide.
      if (msg.type === "ready") {
        listCaptureTargets().catch(() => undefined);
      }
      if (msg.type === "capture_targets") {
        setTargets({
          games: msg.games ?? [],
          windows: msg.windows ?? [],
          monitors: msg.monitors ?? [],
        });
        setTargetsError(null);
      }
      if (msg.type === "error" && msg.message) setActionError(msg.message);
    });
    return () => {
      unlisten.then((f) => f());
    };
  }, []);

  useEffect(() => {
    loadSceneLayout()
      .then(setLayout)
      .catch(() => setLayout(EMPTY_LAYOUT));
  }, []);

  useEffect(() => {
    if (renaming) renameInput.current?.focus();
  }, [renaming]);

  // Le champ de recherche apparaît APRÈS l'ouverture de la fenêtre, quand les cibles
  // arrivent — d'où ce focus posé à son apparition plutôt qu'à l'ouverture.
  useEffect(() => {
    if (addingTo && targets && !chosenIsFile) searchInput.current?.focus();
  }, [addingTo, targets, chosenIsFile]);

  const persist = (next: SceneLayout) => {
    setLayout(next);
    saveSceneLayout(next).catch((error: unknown) =>
      setActionError(String(error)),
    );
  };

  const submitCreate = () => {
    const name = newName.trim();
    if (!name) return;
    setCreateError(null);
    createScene(name)
      .then(() => setNewName(""))
      .catch((error: unknown) => setCreateError(String(error)));
  };

  const activate = (name: string) => {
    setActionError(null);
    switchScene(name).catch((error: unknown) => setActionError(String(error)));
  };

  const confirmDelete = (name: string) => {
    setActionError(null);
    setConfirmingDelete(null);
    deleteScene(name)
      .then(() => {
        // L'étiquette et la position d'une scène disparue n'ont plus de sens : les garder
        // ferait réapparaître un ancien nom si une future scène reprenait cet identifiant.
        const { [name]: _removed, ...labels } = layout.labels;
        persist({ order: layout.order.filter((n) => n !== name), labels });
      })
      .catch((error: unknown) => setActionError(String(error)));
  };

  // Redemandée à chaque ouverture du choix, jamais mise en cache : un jeu lancé entre-temps
  // doit apparaître sans rien redémarrer.
  //
  // L'échec est DIT, jamais avalé : le moteur ne tourne qu'avec le panneau Aperçu ouvert, et
  // afficher « Recherche en cours… » pour toujours laisse l'utilisateur attendre une liste
  // qui ne viendra jamais (même défaut que le panneau Audio, corrigé le 2026-08-04).
  useEffect(() => {
    if (!addingTo) return;
    setTargetsError(null);
    listCaptureTargets().catch(() =>
      setTargetsError(
        "Le moteur n'est pas démarré — ouvre le panneau Aperçu, la liste apparaîtra toute seule.",
      ),
    );
  }, [addingTo]);

  const addToScene = (
    scene: string,
    kind: SourceKind,
    target: CaptureTarget,
  ) => {
    setActionError(null);
    setAddingTo(null);
    // Le libellé lisible sert de nom dans la scène : c'est ce que l'utilisateur reconnaît,
    // et le moteur refuse un doublon.
    addCaptureSource(scene, kind, target.id, target.label).catch(
      (error: unknown) => setActionError(String(error)),
    );
  };

  /** Ouvre le sélecteur du système, puis pose le fichier choisi dans la scène. Un abandon
   * (aucun fichier retenu) ne fait rien et ne dit rien : ce n'est pas une erreur. */
  const pickFile = (scene: string, kind: SourceKind) => {
    setActionError(null);
    open({
      multiple: false,
      filters: [
        {
          name: kind === "image" ? "Images" : "Vidéos",
          extensions: FILE_FILTERS[kind] ?? [],
        },
      ],
    })
      .then((path) => {
        if (typeof path !== "string") return;
        setAddingTo(null);
        return addCaptureSource(scene, kind, path, nameFromPath(path));
      })
      .catch((error: unknown) => setActionError(String(error)));
  };

  // Nommé sans ambiguïté : `reorder` plus bas déplace une SCÈNE dans la liste, celui-ci
  // déplace une SOURCE dans la pile d'une scène. Deux gestes voisins, jamais le même.
  const reorderInScene = (
    scene: string,
    name: string,
    direction: SourceOrder,
  ) => {
    setActionError(null);
    reorderSource(scene, name, direction).catch((error: unknown) =>
      setActionError(String(error)),
    );
  };

  const removeFromScene = (scene: string, name: string) => {
    setActionError(null);
    removeSource(scene, name).catch((error: unknown) =>
      setActionError(String(error)),
    );
  };

  const startRename = (name: string) => {
    setLabelError(null);
    setRenaming(name);
    setDraftLabel(labelFor(name, layout));
  };

  const submitRename = (name: string, sceneNames: string[]) => {
    const verdict = validateLabel(draftLabel, name, sceneNames, layout);
    if (verdict !== "ok") {
      setLabelError(LABEL_ERRORS[verdict]);
      return;
    }
    persist({
      ...layout,
      labels: { ...layout.labels, [name]: draftLabel.trim() },
    });
    setRenaming(null);
  };

  const reorder = (
    sceneNames: string[],
    name: string,
    direction: "up" | "down",
  ) => {
    // L'ordre sauvegardé peut être partiel (scènes créées ailleurs) : on repart de l'ordre
    // AFFICHÉ, seul ordre que l'utilisateur voit et sur lequel il clique.
    persist({ ...layout, order: moveScene(sceneNames, name, direction) });
  };

  const ordered =
    state.status === "ready" ? orderScenes(state.scenes, layout) : [];
  const orderedNames = ordered.map((scene) => scene.name);

  return (
    <div className="flex h-full flex-col gap-4 overflow-y-auto bg-hikari-bg-3 p-6 text-hikari-txt">
      <h3 className="text-[12px] uppercase tracking-wider text-hikari-txt-faint">
        Scènes
      </h3>

      {state.status === "idle" && (
        <p className="text-hikari-txt-faint">
          Ouvre le panneau Aperçu pour gérer les scènes.
        </p>
      )}

      {state.status === "ready" && (
        <ul className="flex flex-col gap-1">
          {ordered.map((scene, index) => {
            const live = scene.name === state.active;
            return (
              <li
                key={scene.name}
                className={`flex flex-col gap-1 rounded-[8px] border px-3 py-2 ${
                  live
                    ? "border-hikari-accent bg-hikari-bg-2"
                    : "border-hikari-line"
                }`}
              >
                <div className="flex items-center justify-between gap-2">
                  {renaming === scene.name ? (
                    <input
                      ref={renameInput}
                      type="text"
                      value={draftLabel}
                      onChange={(event) => setDraftLabel(event.target.value)}
                      onKeyDown={(event) => {
                        if (event.key === "Enter")
                          submitRename(scene.name, orderedNames);
                        if (event.key === "Escape") setRenaming(null);
                      }}
                      onBlur={() => submitRename(scene.name, orderedNames)}
                      aria-label={`Nouveau nom pour ${labelFor(scene.name, layout)}`}
                      className="flex-1 rounded-[6px] border border-hikari-accent bg-hikari-bg px-2 py-1 text-hikari-txt"
                    />
                  ) : (
                    <button
                      type="button"
                      onClick={() => activate(scene.name)}
                      onDoubleClick={() => startRename(scene.name)}
                      disabled={live}
                      title={
                        live ? "Scène en direct" : "Basculer sur cette scène"
                      }
                      className={`flex-1 text-left ${
                        live
                          ? "cursor-default font-medium text-hikari-accent"
                          : "text-hikari-txt hover:text-hikari-accent"
                      }`}
                    >
                      {labelFor(scene.name, layout)}
                      {live && " ● en direct"}
                    </button>
                  )}

                  <div className="flex shrink-0 items-center gap-1">
                    <IconButton
                      label={`Monter ${labelFor(scene.name, layout)}`}
                      disabled={index === 0}
                      onClick={() => reorder(orderedNames, scene.name, "up")}
                    >
                      ↑
                    </IconButton>
                    <IconButton
                      label={`Descendre ${labelFor(scene.name, layout)}`}
                      disabled={index === ordered.length - 1}
                      onClick={() => reorder(orderedNames, scene.name, "down")}
                    >
                      ↓
                    </IconButton>
                    <IconButton
                      label={`Renommer ${labelFor(scene.name, layout)}`}
                      onClick={() => startRename(scene.name)}
                    >
                      ✎
                    </IconButton>
                    <IconButton
                      label={`Supprimer ${labelFor(scene.name, layout)}`}
                      disabled={ordered.length <= 1}
                      onClick={() => setConfirmingDelete(scene.name)}
                    >
                      ✕
                    </IconButton>
                  </div>
                </div>

                <ul className="flex flex-col gap-0.5">
                  {scene.sources.length === 0 ? (
                    <li className="text-[11.5px] text-hikari-txt-faint">
                      Scène vide — ajoute une source ci-dessous.
                    </li>
                  ) : (
                    scene.sources.map((item, position) => (
                      <li
                        key={item.name}
                        className="flex items-center justify-between gap-2 text-[11.5px] text-hikari-txt-faint"
                      >
                        <span className="truncate">
                          {SOURCE_ICON[item.kind] ?? "▪"} {item.name}
                        </span>
                        <span className="flex shrink-0 items-center gap-0.5">
                          <OrderButton
                            label={`Mettre ${item.name} devant`}
                            disabled={position === 0}
                            onClick={() =>
                              reorderInScene(scene.name, item.name, "front")
                            }
                          >
                            ↑
                          </OrderButton>
                          <OrderButton
                            label={`Mettre ${item.name} derrière`}
                            disabled={position === scene.sources.length - 1}
                            onClick={() =>
                              reorderInScene(scene.name, item.name, "back")
                            }
                          >
                            ↓
                          </OrderButton>
                          <button
                            type="button"
                            onClick={() =>
                              removeFromScene(scene.name, item.name)
                            }
                            aria-label={`Retirer ${item.name} de ${labelFor(scene.name, layout)}`}
                            title={`Retirer ${item.name}`}
                            className="px-1 text-hikari-txt-faint transition hover:text-hikari-red"
                          >
                            ✕
                          </button>
                        </span>
                      </li>
                    ))
                  )}
                </ul>
                <p className="text-[11px] text-hikari-txt-faint">
                  {describeContent(scene)}
                </p>
                <button
                  type="button"
                  onClick={() => setAddingTo(scene.name)}
                  className="self-start rounded-[6px] border border-hikari-line px-2 py-0.5 text-[11.5px] text-hikari-txt-dim transition hover:border-hikari-accent hover:text-hikari-txt"
                >
                  + Ajouter une source
                </button>

                {confirmingDelete === scene.name && (
                  <div className="flex items-center justify-between gap-2 rounded-[6px] bg-hikari-bg px-2 py-1.5">
                    <span className="text-[12px] text-hikari-txt-dim">
                      Supprimer « {labelFor(scene.name, layout)} » ?
                    </span>
                    <span className="flex gap-2">
                      <button
                        type="button"
                        onClick={() => setConfirmingDelete(null)}
                        className="text-[12px] text-hikari-txt-dim hover:text-hikari-txt"
                      >
                        Annuler
                      </button>
                      <button
                        type="button"
                        onClick={() => confirmDelete(scene.name)}
                        className="text-[12px] font-medium text-hikari-red hover:brightness-125"
                      >
                        Supprimer
                      </button>
                    </span>
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      )}

      <Modal
        open={addingTo !== null}
        title={
          addingTo ? `Ajouter une source — ${labelFor(addingTo, layout)}` : ""
        }
        onClose={() => setAddingTo(null)}
      >
        {addingTo && (
          <>
            {/* Une seule famille ouverte à la fois : cinq listes dépliées d'un coup
                redonneraient le mur de choix qu'on vient d'éviter. */}
            <div className="flex flex-wrap gap-1.5">
              {SOURCE_FAMILIES.map((family) => (
                <button
                  key={family.kind}
                  type="button"
                  onClick={() => {
                    setFamily(family.kind);
                    setSearch("");
                  }}
                  title={family.hint}
                  aria-pressed={family.kind === chosenFamily}
                  className={`rounded-[6px] border px-2 py-1 text-[12px] transition ${
                    family.kind === chosenFamily
                      ? "border-hikari-accent text-hikari-accent"
                      : "border-hikari-line text-hikari-txt-dim hover:border-hikari-accent hover:text-hikari-txt"
                  }`}
                >
                  {family.label}
                </button>
              ))}
            </div>

            {chosenIsFile ? (
              <button
                type="button"
                data-autofocus
                onClick={() => pickFile(addingTo, chosenFamily)}
                className="self-start rounded-[6px] bg-hikari-accent px-3 py-1.5 text-[12.5px] font-medium text-[#1a1206] transition hover:brightness-110"
              >
                Choisir un fichier…
              </button>
            ) : targetsError ? (
              <p className="text-hikari-red">❌ {targetsError}</p>
            ) : targets === null ? (
              <p className="text-hikari-txt-faint">Recherche en cours…</p>
            ) : (
              <>
                {/* Le focus est posé ICI et non par la fenêtre : quand elle s'ouvre, ce
                    champ n'existe pas encore (la liste des cibles arrive après), donc son
                    autofocus ne trouvait rien à viser. */}
                <input
                  ref={searchInput}
                  type="search"
                  value={search}
                  onChange={(event) => setSearch(event.target.value)}
                  placeholder="Rechercher…"
                  aria-label="Rechercher parmi les sources disponibles"
                  className="rounded-[6px] border border-hikari-line bg-hikari-bg px-2 py-1 text-[12.5px] text-hikari-txt placeholder:text-hikari-txt-faint"
                />
                {(() => {
                  // Dès qu'on tape, on cherche dans TOUTES les familles : quelqu'un qui
                  // tape un nom cherche CETTE chose, pas « cette chose parmi les jeux ».
                  const hits = search.trim()
                    ? searchAll(
                        targets.games,
                        targets.windows,
                        targets.monitors,
                        search,
                      )
                    : dedupeTargets(targetsFor(chosenFamily, targets)).map(
                        (target) => ({ kind: chosenFamily, target }),
                      );
                  if (hits.length === 0) {
                    return (
                      <p className="text-[12px] text-hikari-txt-faint">
                        {search.trim()
                          ? "Rien ne correspond à cette recherche."
                          : "Rien à proposer pour l'instant."}
                      </p>
                    );
                  }
                  return (
                    <ul className="flex flex-col gap-1">
                      {/* La position entre dans la clé : Windows expose plusieurs entrées
                          au MÊME identifiant, et des clés en double empêchaient React de
                          savoir quelle ligne remplacer — la liste restait figée pendant
                          la frappe (vécu 2026-08-05). */}
                      {hits.map((hit, position) => (
                        // biome-ignore lint/suspicious/noArrayIndexKey: la position départage un identifiant, elle ne le remplace pas — Windows expose jusqu'à 12 entrées au MÊME identifiant, et sans ce départage les clés se dupliquent et la liste se fige pendant la frappe (vécu 2026-08-05).
                        <li key={`${hit.kind}:${hit.target.id}:${position}`}>
                          <button
                            type="button"
                            onClick={() =>
                              addToScene(addingTo, hit.kind, hit.target)
                            }
                            className="w-full truncate rounded-[6px] border border-hikari-line px-2 py-1 text-left text-[12.5px] text-hikari-txt-dim transition hover:border-hikari-accent hover:text-hikari-txt"
                          >
                            {SOURCE_ICON[KIND_TO_LIBOBS[hit.kind]] ?? "▪"}{" "}
                            {hit.target.label}
                          </button>
                        </li>
                      ))}
                    </ul>
                  );
                })()}
              </>
            )}
          </>
        )}
      </Modal>

      {labelError && <p className="text-hikari-red">❌ {labelError}</p>}
      {actionError && <p className="text-hikari-red">❌ {actionError}</p>}

      <div className="flex gap-2">
        <input
          type="text"
          value={newName}
          onChange={(event) => setNewName(event.target.value)}
          onKeyDown={(event) => event.key === "Enter" && submitCreate()}
          placeholder="Nom de la nouvelle scène"
          className="flex-1 rounded-[8px] border border-hikari-line bg-hikari-bg px-3 py-1.5 text-hikari-txt placeholder:text-hikari-txt-faint"
        />
        <button
          type="button"
          onClick={submitCreate}
          disabled={!newName.trim()}
          className="rounded-[8px] bg-hikari-accent px-4 py-1.5 font-medium text-[#1a1206] transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-50"
        >
          Créer
        </button>
      </div>
      {createError && <p className="text-hikari-red">❌ {createError}</p>}
    </div>
  );
}

/** One line saying what the scene holds, in plain words — the point of étape 3 point 4:
 * knowing without switching. */
function describeContent(scene: SceneInfo): string {
  if (!scene.has_camera) return "Aucune caméra";
  const filters = [
    scene.background_removal ? "fond IA" : null,
    scene.circle_mask ? "masque cercle" : null,
  ].filter(Boolean);
  return filters.length
    ? `Caméra · ${filters.join(" · ")}`
    : "Caméra · sans filtre";
}

/** Une flèche d'empilement, plus discrète que les boutons de scène pour ne pas confondre
 * « ordre des scènes » et « ordre des sources DANS une scène ». */
function OrderButton({
  label,
  disabled,
  onClick,
  children,
}: {
  label: string;
  disabled?: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      disabled={disabled}
      onClick={onClick}
      className="px-1 text-hikari-txt-faint transition hover:text-hikari-accent disabled:cursor-not-allowed disabled:opacity-30"
    >
      {children}
    </button>
  );
}

/** A small square control. `label` is the accessible name (WCAG 2.2 AA: the glyph alone
 * says nothing to a screen reader), also shown as the tooltip. */
function IconButton({
  label,
  disabled,
  onClick,
  children,
}: {
  label: string;
  disabled?: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      disabled={disabled}
      onClick={onClick}
      className="h-6 w-6 rounded-[6px] border border-hikari-line text-[12px] text-hikari-txt-dim transition hover:border-hikari-accent hover:text-hikari-txt disabled:cursor-not-allowed disabled:opacity-30"
    >
      {children}
    </button>
  );
}
