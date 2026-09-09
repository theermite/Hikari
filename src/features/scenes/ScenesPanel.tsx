// Panneau Scènes (multi-scène, étape 3) — la liste dédiée : créer, basculer, renommer,
// réordonner, supprimer, et voir d'un coup d'œil ce que chaque scène contient.
//
// Partage des rôles : le MOTEUR détient l'existence des scènes et leur contenu (caméra,
// filtres) ; l'APPLICATION détient la présentation (étiquette lisible, ordre d'affichage,
// voir `sceneLayout.ts` pour le pourquoi). Une scène n'est donc jamais renommée côté
// moteur — son identifiant y reste fixe à vie.

import type { IDockviewPanelProps } from "dockview-react";
import { useEffect, useRef, useState } from "react";
import { Panel } from "../../components/ui/Panel";
import type { AudioSourceInfo } from "../audio/types";
import { onAddRequested } from "../shell/panelActions";
import { AddSourceModal } from "./AddSourceModal";
import { createScene, openSettingsWindow } from "./api";
import { SceneRow } from "./SceneRow";
import { SceneCollections, SceneTransition } from "./SceneSkeleton";
import {
  EMPTY_LAYOUT,
  loadSceneLayout,
  moveScene,
  orderScenes,
  type SceneLayout,
  saveSceneLayout,
} from "./sceneLayout";
import { withDefaults } from "./textSettings";
import type { SceneInfo } from "./types";
import { TRANSITION_DURATIONS_MS } from "./types";
import { useAddSource } from "./useAddSource";
import { useEngineSessionSync } from "./useEngineSessionSync";
import { useSceneActions } from "./useSceneActions";
import { useSceneRename } from "./useSceneRename";
import { useTextSettings } from "./useTextSettings";

type State =
  | { status: "idle" }
  | { status: "ready"; scenes: SceneInfo[]; active: string };

/** Un pictogramme par famille de source, pour reconnaître le contenu d'une scène d'un coup
 * d'œil. Clé = identifiant libobs, jamais un nom inventé côté écran. */

/** Le pictogramme d'un résultat de recherche vient de sa famille — un résultat global mêle
 * les familles, il faut donc dire de laquelle il sort. */

export function ScenesPanel(_props: IDockviewPanelProps) {
  const [state, setState] = useState<State>({ status: "idle" });
  const [layout, setLayout] = useState<SceneLayout>(EMPTY_LAYOUT);
  const [newName, setNewName] = useState("");
  const [createError, setCreateError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [confirmingDelete, setConfirmingDelete] = useState<string | null>(null);
  const [addingTo, setAddingTo] = useState<string | null>(null);
  /** La durée de fondu appliquée au PROCHAIN changement de scène (B7) — locale à l'écran,
   * jamais persistée : c'est un réglage du geste, pas de la scène elle-même. Deuxième
   * valeur de `TRANSITION_DURATIONS_MS` (0,3 s), même défaut que la maquette. */
  const [transitionMs, setTransitionMs] = useState<number>(
    TRANSITION_DURATIONS_MS[1],
  );
  /** Les scènes dont les sources sont dépliées. Fermées par défaut : avant, chaque scène
   * déroulait tout son contenu en permanence et trois scènes remplissaient le panneau.
   * La scène EN DIRECT s'ouvre d'office — c'est celle qu'on regarde. */
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  /** Le champ de creation, pour que le « + » de l'onglet y amene directement le curseur. */
  const newNameInput = useRef<HTMLInputElement>(null);
  /** Vrai pendant le rejeu de la session — empêche de réécrire par-dessus ce qu'on restaure. */
  const replaying = useRef(false);
  /** Vrai une fois le rejeu lancé. Tant qu'il est faux, on ne SAUVEGARDE pas : l'état nu du
   * moteur au démarrage écraserait la session qu'on s'apprête justement à lui rendre. */
  const restored = useRef(false);
  /** Vrai seulement quand le rejeu s'est terminé SANS erreur (2026-09-08). Distinct de
   * `restored` : celui-ci passe vrai dès le LANCEMENT du rejeu, avant même sa fin, pour
   * empêcher un second rejeu de démarrer par-dessus. Sans `restoreOk`, une seule commande
   * en échec (un micro pas encore prêt, une caméra momentanément occupée — vu ce soir dans
   * les journaux) arrêtait le rejeu en plein milieu, et l'état TRONQUÉ qui restait devenait
   * la vérité enregistrée au prochain inventaire — écrasant la vraie session sur le disque.
   * Ce champ garde la sauvegarde bloquée tant que ce n'est pas arrivé pour de vrai. */
  const restoreOk = useRef(false);
  /** Le numéro du moteur EN COURS (2026-09-09, relecture) — une vraie ref et non une
   * variable locale à l'effet : sous `React.StrictMode` (`src/main.tsx`), l'effet monte,
   * démonte, remonte, et une variable locale n'aurait plus été LA MÊME entre un rejeu lancé
   * au premier montage et l'incrément suivant. Voir `useEngineSessionSync.ts` pour l'usage. */
  const engineGeneration = useRef(0);
  /** L'état vu par le rejeu. Une référence et non l'état React : le rejeu démarre depuis une
   * fonction de rappel qui a capturé un état déjà périmé. */
  const stateRef = useRef<SceneInfo[]>([]);
  /** Le mixeur vu par la mémoire. Il vit dans un autre panneau, mais la session est UNE
   * chose : la couper en deux fichiers ferait deux états à garder cohérents. */
  const audioRef = useRef<AudioSourceInfo[]>([]);
  /** La scène en direct, pour que l'écoute du mixeur sache quoi retenir sans dépendre d'un
   * état React déjà périmé au moment où elle s'exécute. */
  const activeRef = useRef("main");
  const { textSettings, setTextSettingsFromReplay } = useTextSettings(
    stateRef,
    activeRef,
    audioRef,
  );
  const {
    targets,
    setTargets,
    targetsError,
    setTargetsError,
    chosenFamily,
    setFamily,
    search,
    setSearch,
    draftText,
    setDraftText,
    chosenIsFile,
    searchInput,
    pickerTargets,
    addToScene,
    addText,
    pickFile,
  } = useAddSource(state, addingTo, setAddingTo, setActionError);

  // Le « + » de l'onglet vit hors de l'arbre de ce panneau : il demande, on repond en
  // amenant le curseur là où l'on nomme une scène.
  useEffect(
    () => onAddRequested("scenes", () => newNameInput.current?.focus()),
    [],
  );

  // L'écoute du moteur + le rejeu de session vivent dans `useEngineSessionSync` (extrait
  // le 2026-09-08, plafond de lignes) — comportement inchangé, y compris le garde-fou
  // `restoreOk` qui bloque la sauvegarde tant qu'un rejeu n'a pas RÉUSSI (jamais un rejeu
  // seulement lancé, ou un seul essai sur deux).
  useEngineSessionSync({
    setState,
    stateRef,
    audioRef,
    activeRef,
    replaying,
    restored,
    restoreOk,
    engineGeneration,
    setTextSettingsFromReplay,
    setActionError,
    setTargets,
    setTargetsError,
  });

  useEffect(() => {
    loadSceneLayout()
      .then(setLayout)
      .catch(() => setLayout(EMPTY_LAYOUT));
  }, []);

  // Le champ de recherche apparaît APRÈS l'ouverture de la fenêtre, quand les cibles
  // arrivent — d'où ce focus posé à son apparition plutôt qu'à l'ouverture.
  // biome-ignore lint/correctness/useExhaustiveDependencies: searchInput est une ref stable, inutile au tableau de dépendances.
  useEffect(() => {
    if (addingTo && targets && !chosenIsFile) searchInput.current?.focus();
  }, [addingTo, targets, chosenIsFile]);

  const persist = (next: SceneLayout) => {
    setLayout(next);
    saveSceneLayout(next).catch((error: unknown) =>
      setActionError(String(error)),
    );
  };

  const {
    renaming,
    draftLabel,
    setDraftLabel,
    labelError,
    renameInput,
    startRename,
    submitRename,
    cancelRename,
  } = useSceneRename(layout, persist);

  const submitCreate = () => {
    const name = newName.trim();
    if (!name) return;
    setCreateError(null);
    createScene(name)
      .then(() => setNewName(""))
      .catch((error: unknown) => setCreateError(String(error)));
  };

  const {
    activate,
    confirmDelete,
    reorderInScene,
    removeFromScene,
    toggleLock,
    toggleVisible,
  } = useSceneActions(setActionError, layout, persist, setConfirmingDelete);

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

  /** Ouvre ou ferme les sources d'une scène. La scène en direct reste ouverte d'office :
   * la refermer cacherait justement ce qu'on est en train de diffuser. */
  function toggleExpand(name: string) {
    setExpanded((current) => {
      const next = new Set(current);
      if (next.has(name)) next.delete(name);
      else next.add(name);
      return next;
    });
  }

  return (
    <Panel title="Scènes">
      {state.status === "idle" && (
        <p className="text-hikari-txt-faint">
          Ouvre le panneau Aperçu pour gérer les scènes.
        </p>
      )}

      {/* Les collections coiffent la liste, comme dans la maquette. Elles n'apparaissent
      qu'une fois le moteur entendu : annoncer un groupement au-dessus de rien ferait un
      panneau qui parle de ce qu'il n'a pas. */}
      {state.status === "ready" && <SceneCollections />}

      {state.status === "ready" && (
        <ul className="flex flex-col gap-1">
          {ordered.map((scene, index) => {
            const live = scene.name === state.active;
            return (
              <SceneRow
                key={scene.name}
                scene={scene}
                layout={layout}
                live={live}
                expanded={expanded.has(scene.name) || live}
                onToggleExpand={toggleExpand}
                index={index}
                totalCount={ordered.length}
                orderedNames={orderedNames}
                renaming={renaming}
                draftLabel={draftLabel}
                onDraftLabelChange={setDraftLabel}
                renameInputRef={renameInput}
                confirmingDelete={confirmingDelete}
                onStartRename={startRename}
                onSubmitRename={submitRename}
                onCancelRename={cancelRename}
                onActivate={(name) => activate(name, transitionMs)}
                onReorder={reorder}
                onReorderInScene={reorderInScene}
                onToggleLock={toggleLock}
                onToggleVisible={toggleVisible}
                onRemoveFromScene={removeFromScene}
                onOpenSettings={(sceneName, source) => {
                  const initial =
                    source.source_kind === "text"
                      ? {
                          text: source.target_id,
                          settings: withDefaults(
                            textSettings[sceneName]?.[source.name],
                          ),
                        }
                      : undefined;
                  openSettingsWindow(
                    source.source_kind === "camera" ? "camera" : "text",
                    sceneName,
                    source.name,
                    initial,
                  ).catch((error: unknown) =>
                    console.error("scenes: open_settings_window failed", error),
                  );
                }}
                onAddSource={setAddingTo}
                onRequestDelete={setConfirmingDelete}
                onCancelDelete={() => setConfirmingDelete(null)}
                onConfirmDelete={confirmDelete}
              />
            );
          })}
        </ul>
      )}

      {state.status === "ready" && (
        <SceneTransition value={transitionMs} onChange={setTransitionMs} />
      )}

      <AddSourceModal
        addingTo={addingTo}
        layout={layout}
        chosenFamily={chosenFamily}
        chosenIsFile={chosenIsFile}
        draftText={draftText}
        onDraftTextChange={setDraftText}
        onAddText={addText}
        targets={pickerTargets}
        targetsError={targetsError}
        search={search}
        searchInputRef={searchInput}
        onClose={() => setAddingTo(null)}
        onFamilyChange={(kind) => {
          setFamily(kind);
          setSearch("");
        }}
        onSearchChange={setSearch}
        onPickFile={pickFile}
        onAddToScene={addToScene}
      />

      {labelError && <p className="text-hikari-red">❌ {labelError}</p>}
      {actionError && <p className="text-hikari-red">❌ {actionError}</p>}

      <div className="flex gap-2">
        <input
          type="text"
          ref={newNameInput}
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
    </Panel>
  );
}
