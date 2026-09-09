// L'écoute du moteur + le rejeu de session — extrait de ScenesPanel.tsx le 2026-09-08 (le
// garde-fou de correction de la perte de session a fait dépasser le plafond BLOQUANT de
// 500 lignes). Comportement inchangé : les mêmes refs, le même effet, déplacés tels quels.

import { listen } from "@tauri-apps/api/event";
import { type RefObject, useEffect } from "react";
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
  setMaskShape,
} from "../camera/api";
import {
  addCaptureSource,
  createScene,
  listCaptureTargets,
  requestSceneList,
  setSourceLocked,
  setSourceTransform,
  setTextSettings as setTextSettingsOnEngine,
  switchScene,
} from "./api";
import { loadSession, saveSession } from "./sceneLayout";
import { buildReplay, toSession } from "./session";
import type { TextSettings } from "./textSettings";
import type { CaptureTarget, EngineMessage, SceneInfo } from "./types";

type State =
  | { status: "idle" }
  | { status: "ready"; scenes: SceneInfo[]; active: string };

/** Combien de fois le rejeu réessaie APRÈS le premier échec (2026-09-08), jamais plus : un
 * appareil vraiment indisponible (retiré, en panne) échouerait pour toujours, et retenter
 * sans fin masquerait ce cas au lieu de le signaler. */
const MAX_RESTORE_ATTEMPTS = 2;

/** Relie le panneau au moteur : reçoit ses messages, rejoue la session sauvegardée au
 * démarrage d'un moteur neuf, et enregistre chaque changement — jamais avant la fin d'un
 * rejeu RÉUSSI (`restoreOk`). */
export function useEngineSessionSync(params: {
  setState: (state: State) => void;
  stateRef: RefObject<SceneInfo[]>;
  audioRef: RefObject<AudioSourceInfo[]>;
  activeRef: RefObject<string>;
  replaying: RefObject<boolean>;
  restored: RefObject<boolean>;
  restoreOk: RefObject<boolean>;
  /** Le numéro du moteur EN COURS — voir le commentaire détaillé plus bas, à son usage. */
  engineGeneration: RefObject<number>;
  setTextSettingsFromReplay: (
    updater: (
      avant: Record<string, Record<string, TextSettings>>,
    ) => Record<string, Record<string, TextSettings>>,
  ) => void;
  setActionError: (message: string | null) => void;
  setTargets: (targets: {
    games: CaptureTarget[];
    windows: CaptureTarget[];
    monitors: CaptureTarget[];
  }) => void;
  setTargetsError: (error: string | null) => void;
}) {
  const {
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
  } = params;

  useEffect(() => {
    /** Rend au moteur la session d'avant : il repart vierge à chaque lancement.
     *
     * `engineGeneration` (2026-09-09, relecture) — incrémenté sur chaque `ready`. Un rejeu
     * lancé pour le moteur N ne doit JAMAIS écrire sa conclusion pour le moteur N+1 : sans
     * ce numéro, un moteur qui redémarre PENDANT un rejeu voyait son propre rejeu jeté
     * (`if (replaying.current) return;` refusait de le relancer, `replaying` restant vrai
     * côté ancien rejeu), et c'est l'ANCIEN rejeu — celui du moteur mort — qui finissait par
     * écrire `restoreOk = true` et sauvegarder l'inventaire du NOUVEAU moteur, encore nu.
     * Capturé au début de chaque tentative, comparé à la fin : un rejeu qui se termine pour
     * un moteur qui n'est plus le bon relance lui-même la tentative, pour le bon numéro
     * cette fois — jamais silencieusement jeté. Une VRAIE ref (portée par `ScenesPanel`,
     * jamais une variable locale à l'effet) : sous `React.StrictMode`, l'effet
     * monte/démonte/remonte, et une variable locale n'aurait plus été la même entre un
     * rejeu lancé au premier montage et l'incrément suivant.
     *
     * Réessaie UNE fois sur échec (2026-09-08) : un appareil audio ou une caméra
     * momentanément occupés au lancement (instabilité WASAPI observée en direct le même
     * soir) faisaient échouer une seule commande du milieu du rejeu — et `restoreOk` reste
     * FAUX tant que ce n'est pas résolu, donc rien ne s'enregistre par-dessus la vraie
     * session tant que le second essai n'a pas, lui aussi, tranché.
     *
     * Les étapes sont jouées EN SÉRIE et non en parallèle : chacune dépend de la précédente
     * (on ne remplit pas une scène qui n'existe pas encore), et le moteur les traite dans
     * l'ordre où elles arrivent. */
    const restoreSession = async (
      attempt = 1,
      myGeneration = engineGeneration.current,
    ) => {
      if (replaying.current) return;
      replaying.current = true;
      try {
        const saved = await loadSession();
        // `stateRef.current` porte déjà le progrès du dernier essai (le diff ne redemande
        // que ce qui manque encore) : un second essai REPREND, il ne repart pas de zéro.
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
            await setMaskShape(step.deviceId, step.scene, step.mask);
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
          // Coupe sèche : le rejeu RECONSTRUIT un état déjà connu, ce n'est pas un geste de
          // Jay — un fondu ici ferait attendre l'animation à chaque lancement pour rien.
          if (step.do === "switchScene") await switchScene(step.scene, 0);
        }
        if (myGeneration !== engineGeneration.current) {
          // Ce rejeu vient de finir pour un moteur qui n'est déjà plus le bon (il a
          // redémarré pendant la boucle ci-dessus) — sa réussite ne dit RIEN du moteur
          // actuel. Jeter le résultat plutôt que d'écrire `restoreOk`, et relancer
          // immédiatement pour le bon numéro : c'est ce relais, et non `replaying.current`,
          // qui garantit qu'un rejeu finit toujours par tourner pour le moteur qui existe
          // vraiment.
          replaying.current = false;
          await restoreSession(1, engineGeneration.current);
          return;
        }
        restoreOk.current = true;
      } catch (error: unknown) {
        if (myGeneration !== engineGeneration.current) {
          replaying.current = false;
          await restoreSession(1, engineGeneration.current);
          return;
        }
        if (attempt < MAX_RESTORE_ATTEMPTS) {
          replaying.current = false;
          await restoreSession(attempt + 1, myGeneration);
          return;
        }
        // Deux essais épuisés : signalé, jamais avalé — Jay doit savoir que son cadrage
        // n'a peut-être pas été retrouvé plutôt que de le découvrir en direct. La
        // sauvegarde reprend quand même à partir d'ici : la bloquer pour toujours ferait
        // perdre en silence tout ce que Jay fera ensuite, un défaut pire que celui-ci.
        setActionError(
          `Session non restaurée après ${MAX_RESTORE_ATTEMPTS} essais : ${String(error)}`,
        );
        restoreOk.current = true;
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
        // `restoreOk` ET `restored` : un rejeu LANCÉ mais pas encore RÉUSSI (une commande a
        // échoué, le second essai tourne encore) ne doit pas laisser passer un inventaire
        // tronqué — c'est le défaut qui a écrasé la session de Jay le 2026-09-08.
        if (restored.current && restoreOk.current && !replaying.current) {
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
        // RIEN ne s'écrit tant que la session de CE moteur n'a pas été rejouée avec succès.
        if (
          restored.current &&
          restoreOk.current &&
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
        restoreOk.current = false;
        // Un nouveau numéro de moteur (2026-09-08, relecture) : le rejeu en cours, s'il y
        // en a un, verra à sa fin qu'il ne parle plus du bon moteur et se relancera de
        // lui-même — voir le commentaire de `engineGeneration` plus haut.
        engineGeneration.current += 1;
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

    // Rattrape un panneau qui vient de recharger SANS que le moteur redémarre — un
    // rechargement Vite en dev, ou une actualisation manuelle (2026-09-08 : vécu en
    // direct, écran vide alors qu'une session intacte dormait sur le disque). Rien côté
    // moteur ne renvoie spontanément son état sur un simple rechargement d'écran ; il faut
    // le demander. Envoyée seulement une fois l'écoute confirmée POSÉE (après que `listen`
    // ait résolu) — sinon la réponse pourrait arriver avant que quiconque ne l'attende.
    // Silencieuse si le moteur n'est pas encore démarré : ce n'est pas une panne, juste
    // rien à rattraper.
    unlisten.then(() => {
      requestSceneList().catch(() => undefined);
    });

    return () => {
      unlisten.then((f) => f());
    };
    // Toutes des valeurs STABLES d'un rendu à l'autre (les setters d'état viennent de
    // `useState`, les refs sont les mêmes objets tout au long de la vie du composant) —
    // les lister ici ne refait donc jamais tourner l'effet, ça satisfait seulement le
    // linter sans changer le comportement (identique à l'effet d'origine, déplacé tel quel).
  }, [
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
  ]);
}
