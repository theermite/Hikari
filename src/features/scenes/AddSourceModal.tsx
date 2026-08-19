/**
 * ScenesPanel — la fenêtre d'ajout d'une source : choix de la famille, sélecteur de
 * fichier ou recherche parmi les cibles vivantes proposées par le moteur.
 *
 * Sortie de ScenesPanel.tsx le 2026-08-19 : le fichier faisait 850 lignes, au-dessus du
 * plafond BLOQUANT de 500 (Quality.md). Repris tel quel ; tout ce qui touchait l'état du
 * panneau devient une propriété.
 */

import type { RefObject } from "react";
import { Modal } from "../../components/Modal";
import { KIND_TO_LIBOBS, SOURCE_ICON } from "./ScenesControls";
import { labelFor, type SceneLayout } from "./sceneLayout";
import { dedupeTargets, SOURCE_FAMILIES, searchAll } from "./sourcePicker";
import type { CaptureTarget, SourceKind } from "./types";

export interface CaptureTargets {
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

interface AddSourceModalProps {
  addingTo: string | null;
  layout: SceneLayout;
  chosenFamily: SourceKind;
  chosenIsFile: boolean;
  targets: CaptureTargets | null;
  targetsError: string | null;
  search: string;
  searchInputRef: RefObject<HTMLInputElement | null>;
  onClose: () => void;
  onFamilyChange: (kind: SourceKind) => void;
  onSearchChange: (value: string) => void;
  onPickFile: (scene: string, kind: SourceKind) => void;
  onAddToScene: (
    scene: string,
    kind: SourceKind,
    target: CaptureTarget,
  ) => void;
}

export function AddSourceModal({
  addingTo,
  layout,
  chosenFamily,
  chosenIsFile,
  targets,
  targetsError,
  search,
  searchInputRef,
  onClose,
  onFamilyChange,
  onSearchChange,
  onPickFile,
  onAddToScene,
}: AddSourceModalProps) {
  return (
    <Modal
      open={addingTo !== null}
      title={
        addingTo ? `Ajouter une source — ${labelFor(addingTo, layout)}` : ""
      }
      onClose={onClose}
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
                  onFamilyChange(family.kind);
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
              onClick={() => onPickFile(addingTo, chosenFamily)}
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
                ref={searchInputRef}
                type="search"
                value={search}
                onChange={(event) => onSearchChange(event.target.value)}
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
                            onAddToScene(addingTo, hit.kind, hit.target)
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
  );
}
