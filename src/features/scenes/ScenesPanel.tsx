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
import { Panel } from "../../components/ui/Panel";
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
import { onAddRequested } from "../shell/panelActions";
import { AddSourceModal } from "./AddSourceModal";
import {
  addCaptureSource,
  createScene,
  listCaptureTargets,
  openSettingsWindow,
  setSourceLocked,
  setSourceTransform,
  setTextSettings as setTextSettingsOnEngine,
  switchScene,
} from "./api";
import { SceneRow } from "./SceneRow";
import { SceneCollections, SceneTransition } from "./SceneSkeleton";
import {
  EMPTY_LAYOUT,
  loadSceneLayout,
  loadSession,
  moveScene,
  orderScenes,
  type SceneLayout,
  saveSceneLayout,
  saveSession,
} from "./sceneLayout";
import { buildReplay, toSession } from "./session";
import { withDefaults } from "./textSettings";
import type { EngineMessage, SceneInfo } from "./types";
import { useAddSource } from "./useAddSource";
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
            await setBackgroundRemoval(
              step.deviceId,
              step.scene,
              step.background,
            );
            await setCircleMask(step.deviceId, step.scene, step.circle);
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
          if (step.do === "lock") {
            await setSourceLocked(step.scene, step.name, true);
          }
          if (step.do === "textSettings") {
            // Retenu AUSSI en mémoire : le panneau doit rouvrir sur les vraies valeurs,
            // sinon il afficherait celles de départ sur un texte déjà réglé.
            setTextSettingsFromReplay((avant) => ({
              ...avant,
              [step.scene]: {
                ...(avant[step.scene] ?? {}),
                [step.name]: step.settings,
              },
            }));
            await setTextSettingsOnEngine(step.scene, step.name, step.settings);
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
        // `restored.current` et non seulement « pas de rejeu en cours » : entre le
        // démarrage d'un moteur neuf et le début du rejeu, aucun rejeu ne tourne encore, et
        // c'est précisément là que le mixeur vide du moteur passait — il a effacé les
        // appareils de Jay le 2026-09-07. Une seule règle vaut pour les deux versants :
        // RIEN ne s'écrit tant que la session de CE moteur n'a pas été rejouée.
        if (
          restored.current &&
          !replaying.current &&
          stateRef.current.length > 0
        ) {
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
        // Un moteur NEUF ne connaît que « main ». Sans cette ligne, l'écran prenait son
        // inventaire nu pour la nouvelle vérité et l'écrivait par-dessus les vraies scènes
        // — ce qui a DÉTRUIT la session de Jay le 2026-09-07 quand une correction s'est
        // mise à relancer le moteur en cours de route.
        //
        // La garde d'origine demandait « a-t-on déjà rejoué ? », vraie une fois pour
        // toutes. La bonne question est « ce moteur est-il neuf ? » : elle ferme la
        // famille entière, y compris un moteur qui redémarrerait de lui-même.
        restored.current = false;
      }
      if (msg.type === "capture_targets") {
        setTargets({
          games: msg.games ?? [],
          windows: msg.windows ?? [],
          monitors: msg.monitors ?? [],
        });
        setTargetsError(null);
      }
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
                onActivate={activate}
                onStartRename={startRename}
                onSubmitRename={submitRename}
                onCancelRename={cancelRename}
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

      {state.status === "ready" && <SceneTransition />}

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
