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
import { ComingSoon } from "../../components/ui/ComingSoon";
import { CameraControls } from "../camera/CameraControls";
import { IconButton, OrderButton, SOURCE_ICON } from "./ScenesControls";
import { SceneThumb } from "./SceneThumb";
import { labelFor, type SceneLayout } from "./sceneLayout";
import { TextControls } from "./TextControls";
import { type TextSettings, withDefaults } from "./textSettings";
import type { SceneInfo, SceneSourceInfo, SourceOrder } from "./types";

/** One line saying what the scene holds, in plain words — the point of étape 3 point 4:
 * knowing without switching. */
export function describeContent(scene: SceneInfo): string {
  const cameras = scene.sources.filter((s) => s.source_kind === "camera");
  if (cameras.length === 0) return "Aucune caméra";
  // Plusieurs caméras : on annonce le nombre plutôt que d'énumérer des filtres qui ne
  // s'appliqueraient pas tous à la même — un résumé faux serait pire qu'un résumé court.
  if (cameras.length > 1) return `${cameras.length} caméras`;
  const filters = [
    cameras[0].background_removal ? "fond IA" : null,
    cameras[0].circle_mask ? "masque cercle" : null,
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
  /** Montre ou cache une source sans la retirer — l'œil de la maquette. */
  onToggleVisible: (scene: string, name: string, visible: boolean) => void;
  onRemoveFromScene: (scene: string, name: string) => void;
  /** Ouvre — ou referme — les réglages de CETTE source. Le même bouton pour toutes : une
   * caméra n'a plus son panneau à part (Jay, 2026-09-06). */
  onOpenSettings: (scene: string, source: SceneSourceInfo) => void;
  /** Le nom de la source dont les réglages sont dépliés dans CETTE scène, s'il y en a une. */
  settingsOpenFor: string | null;
  /** Les réglages de texte connus pour CETTE scène, par nom de source. Portés par le parent
   * et non par la ligne : c'est lui qui les retient d'une session à l'autre. */
  textSettings?: Record<string, TextSettings>;
  onTextSettingsChange: (
    scene: string,
    name: string,
    settings: TextSettings,
  ) => void;
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
  onToggleVisible,
  onRemoveFromScene,
  onOpenSettings,
  settingsOpenFor,
  textSettings,
  onTextSettingsChange,
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
      // La maquette pose chaque scène sur une surface ÉLEVÉE (`bg-3`), avec un contour
      // TRANSPARENT qui n'apparaît qu'au survol. C'est le relief qui distingue une ligne
      // de la carte qui la porte ; un contour permanent, lui, fait une grille.
      className={`flex flex-col gap-1 rounded-hikari-s border px-3 py-2.5 transition ${
        live
          ? "border-hikari-accent bg-hikari-accent/[.14]"
          : "border-transparent bg-hikari-bg-3 hover:border-hikari-line"
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
                  className="flex flex-wrap items-center justify-between gap-2 rounded-[6px] px-2 py-1 text-[12.5px] text-hikari-txt-dim transition hover:bg-hikari-bg-3"
                >
                  <span
                    className={`truncate ${item.visible ? "" : "line-through opacity-50"}`}
                  >
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
                    {/* L'œil de la maquette. Premier de la rangée : c'est le geste le
                    plus fréquent en direct, et le seul entièrement réversible d'un clic.
                    L'état est porté par le bouton lui-même — un pictogramme d'œil barré
                    ne se lit pas à voix haute. */}
                    <button
                      type="button"
                      onClick={() =>
                        onToggleVisible(scene.name, item.name, !item.visible)
                      }
                      aria-label={
                        item.visible
                          ? `Cacher ${item.name}`
                          : `Montrer ${item.name}`
                      }
                      aria-pressed={item.visible}
                      title={
                        item.visible
                          ? `Cacher ${item.name} — elle garde son cadrage et ses filtres`
                          : `Montrer ${item.name}`
                      }
                      className={`px-1 transition ${
                        item.visible
                          ? "text-hikari-txt-faint hover:text-hikari-txt"
                          : "text-hikari-txt-faint/40 hover:text-hikari-txt-faint"
                      }`}
                    >
                      {item.visible ? "👁" : "🚫"}
                    </button>
                    {/* Les réglages sont là où la source est. Le 2026-09-06, une caméra
                    les portait dans un panneau à part, et ils sont devenus inatteignables
                    dès que ce panneau a perdu le fil de la scène en direct. */}
                    {item.source_kind === "camera" ||
                    item.source_kind === "text" ? (
                      <button
                        type="button"
                        onClick={() => onOpenSettings(scene.name, item)}
                        aria-label={`Réglages de ${item.name}`}
                        title={`Réglages de ${item.name}`}
                        className="px-1 text-hikari-txt-faint transition hover:text-hikari-accent"
                      >
                        ⚙
                      </button>
                    ) : (
                      <ComingSoon what="les réglages de cette source">
                        <button
                          type="button"
                          disabled
                          aria-label={`Réglages de ${item.name}`}
                          className="px-1 text-hikari-txt-faint"
                        >
                          ⚙
                        </button>
                      </ComingSoon>
                    )}
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
                  {/* Dépliés SOUS la ligne, jamais dans une fenêtre : l'image du moteur
                  est une fenêtre NATIVE, elle se dessine au-dessus de tout contenu web,
                  donc une fenêtre par-dessus l'oblige à se retirer de l'écran. Régler une
                  caméra sans la voir n'a pas de sens (Jay, 2026-09-06). */}
                  {settingsOpenFor === item.name &&
                    item.source_kind === "text" && (
                      <TextControls
                        scene={scene.name}
                        name={item.name}
                        text={item.target_id}
                        settings={withDefaults(textSettings?.[item.name])}
                        onChange={(next) =>
                          onTextSettingsChange(scene.name, item.name, next)
                        }
                      />
                    )}
                  {settingsOpenFor === item.name &&
                    item.source_kind === "camera" && (
                      <CameraControls
                        scene={scene.name}
                        camera={{
                          deviceId: item.target_id,
                          name: item.name,
                          backgroundRemoval: item.background_removal,
                          circleMask: item.circle_mask,
                        }}
                      />
                    )}
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
