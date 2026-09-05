/**
 * ScenesPanel — la ligne d'une scène : nom (avec renommage), réordonnancement, suppression,
 * liste des sources qu'elle contient, ajout d'une source.
 *
 * Sortie de ScenesPanel.tsx le 2026-08-19 : le fichier faisait 850 lignes, au-dessus du
 * plafond BLOQUANT de 500 (Quality.md). Toutes les fonctions qui touchent l'état du
 * panneau sont des propriétés — ce composant n'a aucun état propre, tout vit dans
 * ScenesPanel.
 *
 * Reconstruit le 2026-09-05 à l'image de la maquette (Jay : « on est toujours loin de la
 * maquette »). Ce qui change, et pourquoi :
 *   - une VIGNETTE ouvre la ligne, comme dans la maquette ;
 *   - les sources sont REPLIÉES par défaut. Avant, chaque scène déroulait tout son
 *     contenu en permanence : trois scènes remplissaient l'écran et le panneau devenait
 *     illisible. La scène en direct s'ouvre d'office — c'est celle qu'on regarde ;
 *   - la ligne entière bascule la scène, au lieu du seul nom. La maquette promet « 1 clic ».
 */

import type { RefObject } from "react";
import { IconButton, OrderButton, SOURCE_ICON } from "./ScenesControls";
import { SceneThumb } from "./SceneThumb";
import { labelFor, type SceneLayout } from "./sceneLayout";
import type { SceneInfo, SourceOrder } from "./types";

/** One line saying what the scene holds, in plain words — the point of étape 3 point 4:
 * knowing without switching. */
export function describeContent(scene: SceneInfo): string {
  if (!scene.has_camera) return "Aucune caméra";
  const filters = [
    scene.background_removal ? "fond IA" : null,
    scene.circle_mask ? "masque cercle" : null,
  ].filter(Boolean);
  return filters.length
    ? `Caméra · ${filters.join(" · ")}`
    : "Caméra · sans filtre";
}

interface SceneRowProps {
  scene: SceneInfo;
  layout: SceneLayout;
  live: boolean;
  /** Sources dépliées ou non. L'état vit dans ScenesPanel : cette ligne n'en a aucun. */
  expanded: boolean;
  onToggleExpand: (scene: string) => void;
  index: number;
  totalCount: number;
  orderedNames: string[];
  renaming: string | null;
  draftLabel: string;
  onDraftLabelChange: (value: string) => void;
  renameInputRef: RefObject<HTMLInputElement | null>;
  confirmingDelete: string | null;
  onActivate: (name: string) => void;
  onStartRename: (name: string) => void;
  onSubmitRename: (name: string, sceneNames: string[]) => void;
  onCancelRename: () => void;
  onReorder: (
    sceneNames: string[],
    name: string,
    direction: "up" | "down",
  ) => void;
  onReorderInScene: (
    scene: string,
    name: string,
    direction: SourceOrder,
  ) => void;
  onToggleLock: (scene: string, name: string, locked: boolean) => void;
  onRemoveFromScene: (scene: string, name: string) => void;
  onAddSource: (scene: string) => void;
  onRequestDelete: (name: string) => void;
  onCancelDelete: () => void;
  onConfirmDelete: (name: string) => void;
}

export function SceneRow({
  scene,
  layout,
  live,
  expanded,
  onToggleExpand,
  index,
  totalCount,
  orderedNames,
  renaming,
  draftLabel,
  onDraftLabelChange,
  renameInputRef,
  confirmingDelete,
  onActivate,
  onStartRename,
  onSubmitRename,
  onCancelRename,
  onReorder,
  onReorderInScene,
  onToggleLock,
  onRemoveFromScene,
  onAddSource,
  onRequestDelete,
  onCancelDelete,
  onConfirmDelete,
}: SceneRowProps) {
  return (
    // Le nom de la scène est porté par la LIGNE, pas seulement par son bouton : c'est ce
    // qui permet à un lecteur d'écran d'annoncer « scène Chat Ermite » en arrivant dessus,
    // et de la retrouver sans dépendre de l'ordre du texte à l'intérieur.
    <li
      aria-label={labelFor(scene.name, layout)}
      className={`flex flex-col gap-1 rounded-[8px] border px-3 py-2 ${
        live
          ? "border-hikari-accent bg-hikari-accent/[.07]"
          : "border-hikari-line"
      }`}
    >
      <div className="flex items-center gap-2">
        <SceneThumb scene={scene} live={live} />
        {renaming === scene.name ? (
          <input
            ref={renameInputRef}
            type="text"
            value={draftLabel}
            onChange={(event) => onDraftLabelChange(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter")
                onSubmitRename(scene.name, orderedNames);
              if (event.key === "Escape") onCancelRename();
            }}
            onBlur={() => onSubmitRename(scene.name, orderedNames)}
            aria-label={`Nouveau nom pour ${labelFor(scene.name, layout)}`}
            className="flex-1 rounded-[6px] border border-hikari-accent bg-hikari-bg px-2 py-1 text-hikari-txt"
          />
        ) : (
          <button
            type="button"
            onClick={() => onActivate(scene.name)}
            onDoubleClick={() => onStartRename(scene.name)}
            disabled={live}
            title={live ? "Scène en direct" : "Basculer sur cette scène"}
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
            label={
              expanded
                ? `Replier ${labelFor(scene.name, layout)}`
                : `Déplier ${labelFor(scene.name, layout)}`
            }
            pressed={expanded}
            onClick={() => onToggleExpand(scene.name)}
          >
            {expanded ? "▾" : "▸"}
          </IconButton>
          <IconButton
            label={`Monter ${labelFor(scene.name, layout)}`}
            disabled={index === 0}
            onClick={() => onReorder(orderedNames, scene.name, "up")}
          >
            ↑
          </IconButton>
          <IconButton
            label={`Descendre ${labelFor(scene.name, layout)}`}
            disabled={index === totalCount - 1}
            onClick={() => onReorder(orderedNames, scene.name, "down")}
          >
            ↓
          </IconButton>
          <IconButton
            label={`Renommer ${labelFor(scene.name, layout)}`}
            onClick={() => onStartRename(scene.name)}
          >
            ✎
          </IconButton>
          <IconButton
            label={`Supprimer ${labelFor(scene.name, layout)}`}
            disabled={totalCount <= 1}
            onClick={() => onRequestDelete(scene.name)}
          >
            ✕
          </IconButton>
        </div>
      </div>

      {expanded ? (
        <>
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
                        onReorderInScene(scene.name, item.name, "front")
                      }
                    >
                      ↑
                    </OrderButton>
                    <OrderButton
                      label={`Mettre ${item.name} derrière`}
                      disabled={position === scene.sources.length - 1}
                      onClick={() =>
                        onReorderInScene(scene.name, item.name, "back")
                      }
                    >
                      ↓
                    </OrderButton>
                    <button
                      type="button"
                      onClick={() =>
                        onToggleLock(scene.name, item.name, !item.locked)
                      }
                      aria-label={
                        item.locked
                          ? `Libérer ${item.name} dans ${labelFor(scene.name, layout)}`
                          : `Figer ${item.name} dans ${labelFor(scene.name, layout)}`
                      }
                      aria-pressed={item.locked}
                      title={
                        item.locked
                          ? `${item.name} est figée — cliquer pour la libérer`
                          : `Figer ${item.name} : plus déplaçable à la souris`
                      }
                      className={`px-1 transition ${
                        item.locked
                          ? "text-hikari-accent"
                          : "text-hikari-txt-faint hover:text-hikari-txt"
                      }`}
                    >
                      {item.locked ? "🔒" : "🔓"}
                    </button>
                    <button
                      type="button"
                      onClick={() => onRemoveFromScene(scene.name, item.name)}
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
            onClick={() => onAddSource(scene.name)}
            className="self-start rounded-[6px] border border-hikari-line px-2 py-0.5 text-[11.5px] text-hikari-txt-dim transition hover:border-hikari-accent hover:text-hikari-txt"
          >
            + Ajouter une source
          </button>
        </>
      ) : null}

      {confirmingDelete === scene.name && (
        <div className="flex items-center justify-between gap-2 rounded-[6px] bg-hikari-bg px-2 py-1.5">
          <span className="text-[12px] text-hikari-txt-dim">
            Supprimer « {labelFor(scene.name, layout)} » ?
          </span>
          <span className="flex gap-2">
            <button
              type="button"
              onClick={onCancelDelete}
              className="text-[12px] text-hikari-txt-dim hover:text-hikari-txt"
            >
              Annuler
            </button>
            <button
              type="button"
              onClick={() => onConfirmDelete(scene.name)}
              className="text-[12px] font-medium text-hikari-red hover:brightness-125"
            >
              Supprimer
            </button>
          </span>
        </div>
      )}
    </li>
  );
}
