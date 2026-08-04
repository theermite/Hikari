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
import { createScene, deleteScene, switchScene } from "./api";
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
import type { EngineMessage, SceneInfo } from "./types";

type State =
  | { status: "idle" }
  | { status: "ready"; scenes: SceneInfo[]; active: string };

const LABEL_ERRORS = {
  empty: "Le nom ne peut pas être vide.",
  duplicate: "Une autre scène porte déjà ce nom.",
} as const;

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
  const renameInput = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const unlisten = listen<EngineMessage>("engine-message", (event) => {
      const msg = event.payload;
      if (msg.type === "scene_list" && msg.scenes && msg.active) {
        setState({ status: "ready", scenes: msg.scenes, active: msg.active });
      }
      // Le moteur refuse lui-même la suppression interdite : on affiche SA raison plutôt
      // que d'inventer un message côté écran.
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

                <p className="text-[11.5px] text-hikari-txt-faint">
                  {describeContent(scene)}
                </p>

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
