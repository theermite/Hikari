// Panneau Scènes (multi-scène, étape 3) — la liste dédiée : créer, basculer, renommer,
// réordonner, supprimer, et voir d'un coup d'œil ce que chaque scène contient.
//
// Partage des rôles : le MOTEUR détient l'existence des scènes et leur contenu (caméra,
// filtres) ; l'APPLICATION détient la présentation (étiquette lisible, ordre d'affichage,
// voir `sceneLayout.ts` pour le pourquoi). Une scène n'est donc jamais renommée côté
// moteur — son identifiant y reste fixe à vie.

import { listen } from "@tauri-apps/api/event";
import type { IDockviewPanelProps } from "dockview-react";
import { useEffect, useRef, useState } from "react";
import { Modal } from "../../components/Modal";
import {
  addCaptureSource,
  createScene,
  deleteScene,
  listCaptureTargets,
  removeSource,
  switchScene,
} from "./api";
import {
  EMPTY_LAYOUT,
  labelFor,
  loadSceneLayout,
  moveScene,
  orderScenes,
  type SceneLayout,
  saveSceneLayout,
  validateLabel,
} from "./sceneLayout";
import type {
  CaptureKind,
  CaptureTarget,
  EngineMessage,
  SceneInfo,
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

/** Les trois familles proposées à l'ajout, dites par ce qu'elles montrent. */
const CAPTURE_FAMILIES: {
  kind: CaptureKind;
  label: string;
  hint: string;
  pick: (t: CaptureTargets) => CaptureTarget[];
}[] = [
  {
    kind: "game",
    label: "Un jeu",
    hint: "Accroche le jeu directement — la voie la plus fluide.",
    pick: (t) => t.games,
  },
  {
    kind: "window",
    label: "Une fenêtre",
    hint: "N'importe quelle fenêtre ouverte, même hors jeu.",
    pick: (t) => t.windows,
  },
  {
    kind: "monitor",
    label: "Un écran",
    hint: "Tout un écran, choisi parmi les tiens.",
    pick: (t) => t.monitors,
  },
];

interface CaptureTargets {
  games: CaptureTarget[];
  windows: CaptureTarget[];
  monitors: CaptureTarget[];
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
  const renameInput = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const unlisten = listen<EngineMessage>("engine-message", (event) => {
      const msg = event.payload;
      if (msg.type === "scene_list" && msg.scenes && msg.active) {
        setState({ status: "ready", scenes: msg.scenes, active: msg.active });
      }
      // Le moteur refuse lui-même la suppression interdite : on affiche SA raison plutôt
      // que d'inventer un message côté écran.
      if (msg.type === "capture_targets") {
        setTargets({
          games: msg.games ?? [],
          windows: msg.windows ?? [],
          monitors: msg.monitors ?? [],
        });
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
  useEffect(() => {
    if (addingTo) listCaptureTargets().catch(() => undefined);
  }, [addingTo]);

  const addToScene = (
    scene: string,
    kind: CaptureKind,
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
                    scene.sources.map((item) => (
                      <li
                        key={item.name}
                        className="flex items-center justify-between gap-2 text-[11.5px] text-hikari-txt-faint"
                      >
                        <span className="truncate">
                          {SOURCE_ICON[item.kind] ?? "▪"} {item.name}
                        </span>
                        <button
                          type="button"
                          onClick={() => removeFromScene(scene.name, item.name)}
                          aria-label={`Retirer ${item.name} de ${labelFor(scene.name, layout)}`}
                          title={`Retirer ${item.name}`}
                          className="shrink-0 px-1 text-hikari-txt-faint transition hover:text-hikari-red"
                        >
                          ✕
                        </button>
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
            {targets === null && (
              <p className="text-hikari-txt-faint">Recherche en cours…</p>
            )}
            {targets !== null &&
              CAPTURE_FAMILIES.map((family) => {
                const list = family.pick(targets);
                return (
                  <div key={family.kind} className="flex flex-col gap-1.5">
                    <h3
                      className="text-[11px] uppercase tracking-wider text-hikari-txt-faint"
                      title={family.hint}
                    >
                      {family.label}
                    </h3>
                    {list.length === 0 ? (
                      <p className="text-[12px] text-hikari-txt-faint">
                        Rien à proposer pour l'instant.
                      </p>
                    ) : (
                      <ul className="flex flex-col gap-1">
                        {list.map((target) => (
                          <li key={`${family.kind}:${target.id}`}>
                            <button
                              type="button"
                              onClick={() =>
                                addToScene(addingTo, family.kind, target)
                              }
                              className="w-full truncate rounded-[6px] border border-hikari-line px-2 py-1 text-left text-[12.5px] text-hikari-txt-dim transition hover:border-hikari-accent hover:text-hikari-txt"
                            >
                              {
                                SOURCE_ICON[
                                  family.kind === "game"
                                    ? "game_capture"
                                    : family.kind === "window"
                                      ? "window_capture"
                                      : "monitor_capture"
                                ]
                              }{" "}
                              {target.label}
                            </button>
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                );
              })}
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
