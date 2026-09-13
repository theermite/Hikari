// Ce que la maquette dessine dans le panneau Scènes.
//
// Décision de Jay, 2026-09-05 : dessiner le squelette complet et le marquer « à venir »
// quand une pièce n'est pas encore branchée, plutôt que de laisser des trous.
//
// Les COLLECTIONS groupent les scènes par contexte (jeu, interview, pause) — brique livrée
// le 2026-09-13, pure présentation app (`sceneLayout.ts`), rien à demander au moteur.
// La TRANSITION (fondu au changement de scène, B7) est branchée depuis 2026-09-08 —
// `ScenesPanel` lui passe la durée choisie et le changement.

import { useState } from "react";
import {
  createCollection,
  deleteCollection,
  renameCollection,
  type SceneLayout,
  toggleSceneInCollection,
  validateCollectionName,
} from "./sceneLayout";
import { TRANSITION_DURATION_LABEL, TRANSITION_DURATIONS_MS } from "./types";

/** Un champ de saisie qui se ferme sur Entrée ou Échap — même geste que la création d'une
 * scène en bas du panneau, jamais un second clic « valider » à chercher. */
function NameField({
  placeholder,
  initial = "",
  onSubmit,
  onCancel,
}: {
  placeholder: string;
  initial?: string;
  onSubmit: (value: string) => void;
  onCancel: () => void;
}) {
  const [value, setValue] = useState(initial);
  // Apparaît sur un geste explicite (bouton « Créer », double-clic pour renommer) : le
  // focus suit l'intention de l'utilisateur, jamais un geste que la page fait seule.
  return (
    <input
      // biome-ignore lint/a11y/noAutofocus: geste explicite, voir le commentaire au-dessus.
      autoFocus
      type="text"
      value={value}
      placeholder={placeholder}
      onChange={(event) => setValue(event.target.value)}
      onBlur={() => (value.trim() ? onSubmit(value) : onCancel())}
      onKeyDown={(event) => {
        if (event.key === "Enter") onSubmit(value);
        if (event.key === "Escape") onCancel();
      }}
      className="rounded-full border border-hikari-accent bg-hikari-bg px-2.5 py-0.5 text-[12px] text-hikari-txt outline-none"
    />
  );
}

/** Les onglets de collections, tels que la maquette les pose au-dessus des scènes —
 * « Toutes » d'abord (jamais une scène cachée par erreur), puis une par collection, puis
 * de quoi en créer une. Tant qu'aucune n'existe, un seul bouton « Créer une collection »
 * — pas des onglets vides qui parlent de rien (Jay, 2026-09-13). */
export function SceneCollections({
  layout,
  sceneNames,
  labelFor,
  activeId,
  onSelectTab,
  onPersist,
}: {
  layout: SceneLayout;
  /** Les scènes RÉELLEMENT vivantes côté moteur — la case à cocher ne propose jamais une
   * scène supprimée ou pas encore connue. */
  sceneNames: string[];
  labelFor: (name: string) => string;
  activeId: string | null;
  onSelectTab: (id: string | null) => void;
  onPersist: (next: SceneLayout) => void;
}) {
  const [creating, setCreating] = useState(false);
  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [managingId, setManagingId] = useState<string | null>(null);
  const [nameError, setNameError] = useState<string | null>(null);

  const collections = layout.collections ?? [];

  const submitCreate = (name: string) => {
    if (validateCollectionName(name, layout) !== "ok") {
      setNameError(name.trim() ? "Ce nom existe déjà." : null);
      if (!name.trim()) setCreating(false);
      return;
    }
    setNameError(null);
    setCreating(false);
    onPersist(createCollection(layout, name));
  };

  const submitRename = (id: string, name: string) => {
    if (validateCollectionName(name, layout, id) !== "ok") {
      setNameError(name.trim() ? "Ce nom existe déjà." : null);
      if (!name.trim()) setRenamingId(null);
      return;
    }
    setNameError(null);
    setRenamingId(null);
    onPersist(renameCollection(layout, id, name));
  };

  if (collections.length === 0 && !creating) {
    return (
      <button
        type="button"
        onClick={() => setCreating(true)}
        className="mb-2.5 self-start rounded-full border border-hikari-line px-2.5 py-1 text-[12px] text-hikari-txt-dim hover:text-hikari-txt"
      >
        + Créer une collection
      </button>
    );
  }

  const active = collections.find((collection) => collection.id === managingId);

  return (
    <div className="mb-2.5 flex flex-col gap-1.5">
      <ul
        aria-label="Collections de scènes"
        className="flex flex-wrap gap-1.5 text-[12px]"
      >
        <li>
          <button
            type="button"
            onClick={() => onSelectTab(null)}
            aria-pressed={activeId === null}
            className={`rounded-full border px-2.5 py-0.5 ${
              activeId === null
                ? "border-hikari-accent text-hikari-accent"
                : "border-hikari-line text-hikari-txt-dim hover:text-hikari-txt"
            }`}
          >
            Toutes
          </button>
        </li>
        {collections.map((collection) =>
          renamingId === collection.id ? (
            <li key={collection.id}>
              <NameField
                placeholder="Nom de la collection"
                initial={collection.name}
                onSubmit={(name) => submitRename(collection.id, name)}
                onCancel={() => setRenamingId(null)}
              />
            </li>
          ) : (
            <li key={collection.id} className="flex items-center gap-1">
              <button
                type="button"
                onClick={() => onSelectTab(collection.id)}
                onDoubleClick={() => setRenamingId(collection.id)}
                aria-pressed={activeId === collection.id}
                title="Double-clique pour renommer"
                className={`rounded-full border px-2.5 py-0.5 ${
                  activeId === collection.id
                    ? "border-hikari-accent text-hikari-accent"
                    : "border-hikari-line text-hikari-txt-dim hover:text-hikari-txt"
                }`}
              >
                {collection.name}
              </button>
              {activeId === collection.id && (
                <>
                  <button
                    type="button"
                    onClick={() => setManagingId(collection.id)}
                    title="Choisir les scènes de cette collection"
                    className="text-hikari-txt-faint hover:text-hikari-txt-dim"
                  >
                    🏷️
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      onPersist(deleteCollection(layout, collection.id));
                      onSelectTab(null);
                    }}
                    title="Supprimer cette collection (les scènes restent)"
                    className="text-hikari-txt-faint hover:text-hikari-red"
                  >
                    ✕
                  </button>
                </>
              )}
            </li>
          ),
        )}
        <li>
          {creating ? (
            <NameField
              placeholder="Nom de la collection"
              onSubmit={submitCreate}
              onCancel={() => setCreating(false)}
            />
          ) : (
            <button
              type="button"
              onClick={() => setCreating(true)}
              title="Créer une collection"
              className="rounded-full border border-hikari-line px-2 py-0.5 text-hikari-txt-dim hover:text-hikari-txt"
            >
              +
            </button>
          )}
        </li>
      </ul>
      {nameError && <p className="text-[11px] text-hikari-red">{nameError}</p>}

      {active && (
        <div className="rounded-[8px] border border-hikari-line bg-hikari-bg p-2">
          <p className="mb-1 text-[11px] text-hikari-txt-faint">
            Scènes dans « {active.name} »
          </p>
          <ul className="flex flex-col gap-0.5">
            {sceneNames.map((name) => (
              <li key={name}>
                <label className="flex items-center gap-1.5 text-[12px] text-hikari-txt">
                  <input
                    type="checkbox"
                    checked={active.sceneNames.includes(name)}
                    onChange={() =>
                      onPersist(
                        toggleSceneInCollection(layout, active.id, name),
                      )
                    }
                  />
                  {labelFor(name)}
                </label>
              </li>
            ))}
          </ul>
          <button
            type="button"
            onClick={() => setManagingId(null)}
            className="mt-1 text-[11px] text-hikari-txt-faint hover:text-hikari-txt-dim"
          >
            Fermer
          </button>
        </div>
      )}
    </div>
  );
}

/** La ligne « Transition », en bas du panneau — la durée du fondu appliqué au prochain
 * changement de scène (B7). `value` est TOUJOURS l'une de `TRANSITION_DURATIONS_MS` : le
 * `<select>` n'offre que ces options, donc rien d'autre ne peut en sortir. */
export function SceneTransition({
  value,
  onChange,
}: {
  value: number;
  onChange: (durationMs: number) => void;
}) {
  return (
    <div className="mt-1 border-t border-hikari-line pt-2">
      <label className="flex items-center gap-2 text-[12px] text-hikari-txt-dim">
        🎬 Transition
        <select
          value={value}
          onChange={(event) => onChange(Number(event.target.value))}
          className="rounded-[6px] border border-hikari-line bg-hikari-bg px-2 py-0.5 text-hikari-txt"
        >
          {TRANSITION_DURATIONS_MS.map((ms) => (
            <option key={ms} value={ms}>
              {TRANSITION_DURATION_LABEL[ms]}
            </option>
          ))}
        </select>
      </label>
    </div>
  );
}
