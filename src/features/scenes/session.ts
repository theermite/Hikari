// Mémoire de session (brique Persistance) — ce qui survit à la fermeture de l'app.
//
// POURQUOI côté application et non côté moteur : le moteur repart de zéro à chaque
// lancement, par conception (il ne tourne qu'à la demande, ADR-013). L'app, elle, reçoit
// déjà l'état complet à chaque changement — elle est donc la seule à pouvoir le retenir puis
// le rejouer. Le moteur reste sans mémoire, ce qui garde une seule source de vérité.
//
// Le REJEU est un diff, jamais un écrasement : au démarrage, le moteur a déjà une scène
// « main » avec sa capture d'écran. Rejouer aveuglément tenterait de la recréer et se ferait
// refuser. On ne demande donc que ce qui manque.

import type {
  AudioMonitoring,
  AudioSourceInfo,
  AudioSourceKind,
  NoiseMethod,
} from "../audio/types";
import type { TextSettings } from "./textSettings";
import {
  type MaskShape,
  NO_MASK,
  type SceneInfo,
  type SourceKind,
} from "./types";

/** Une source telle qu'on la retrouvera au prochain lancement. */
export interface SavedSource {
  name: string;
  kind: SourceKind;
  targetId: string;
  x: number;
  y: number;
  scalePercent: number;
  /** Figée à la souris. Absent des sessions écrites avant le 2026-08-06 : l'absence vaut
   * « libre », jamais « verrouillée » — personne n'a demandé à figer l'existant. */
  locked?: boolean;
  /** L'apparence d'une source TEXTE. Absent partout ailleurs, et absent des sessions
   * écrites avant le 2026-09-07 : la lecture complète alors avec les valeurs de départ,
   * jamais avec du vide — un champ ajouté à une donnée déjà rangée sans défaut de lecture
   * casse l'application de ceux qui ont l'ancienne version. */
  text?: TextSettings;
}

export interface SavedScene {
  name: string;
  sources: SavedSource[];
  /** Les caméras de cette scène, depuis le 2026-09-06. */
  cameras?: SavedCamera[];
  /** L'unique caméra des sessions écrites AVANT le 2026-09-06.
   *
   * Gardé en lecture seule : une session déjà sur le disque de Jay porte ce champ, et le
   * supprimer lui ferait perdre son cadrage au prochain lancement — sans erreur, sans que
   * rien ne l'explique. Lu par `camerasOf`, plus jamais écrit. */
  camera?: SavedCamera;
}

/** Les caméras d'une scène enregistrée, quel que soit l'âge du fichier. */
export function camerasOf(scene: SavedScene): SavedCamera[] {
  if (scene.cameras) return scene.cameras;
  return scene.camera ? [scene.camera] : [];
}

/** Une caméra d'une scène : un appareil, avec un cadrage et des filtres propres à CETTE
 * scène — c'est exactement le flux que Jay utilise. */
export interface SavedCamera {
  deviceId: string;
  /** Le nom que le moteur donne à la source caméra. Retenu parce que replacer un objet
   * exige de savoir le nommer — sans lui, le cadrage ci-dessous ne serait adressable par
   * aucune commande au rejeu. Absent des sessions écrites avant le 2026-08-06. */
  name?: string;
  backgroundRemoval: boolean;
  /** La forme de masque, depuis le 2026-09-09. Absent des sessions écrites avant cette
   * date — lire `maskShapeOf(camera)`, jamais ce champ directement. */
  maskShape?: MaskShape;
  /** Le SEUL champ qu'écrivaient les sessions d'avant le 2026-09-09 (un simple cercle
   * on/off). Gardé en lecture seule, comme `camera?` plus haut : le supprimer ferait
   * perdre le masque de Jay au premier lancement de cette version. Jamais réécrit —
   * `maskShapeOf` migre vers `maskShape` dès la première sauvegarde qui suit. */
  circleMask?: boolean;
  x: number;
  y: number;
  scalePercent: number;
  /** Figée à la souris dans cette scène. Même règle d'absence que pour les captures. */
  locked?: boolean;
}

/** La forme de masque d'une caméra enregistrée, quel que soit l'âge du fichier — même
 * rôle que `camerasOf` pour les caméras elles-mêmes. */
export function maskShapeOf(camera: SavedCamera): MaskShape {
  if (camera.maskShape) return camera.maskShape;
  if (camera.circleMask) return { kind: "circle" };
  return NO_MASK;
}

/** Le nom de repli quand une session ancienne ne porte pas celui de sa caméra
 * (`CAMERA_SOURCE_NAME`, côté moteur — à l'époque une seule caméra, donc un seul nom
 * possible). Le test `should_keep_the_camera_name_the_session_replay_falls_back_to` casse
 * si l'autre côté de la frontière change cette valeur sans qu'on touche à celle-ci. */
const DEFAULT_CAMERA_NAME = "Webcam";

/** Une entrée du mixeur telle qu'on la retrouvera. */
export interface SavedAudio {
  name: string;
  kind: AudioSourceKind;
  deviceId: string;
  volumePercent: number;
  monitorVolumePercent: number;
  muted: boolean;
  monitoring: AudioMonitoring;
  noiseSuppression: boolean;
  noiseMethod: NoiseMethod;
  noiseLevelDb: number;
}

export interface SessionDoc {
  scenes: SavedScene[];
  active: string;
  audio: SavedAudio[];
}

export const EMPTY_SESSION: SessionDoc = {
  scenes: [],
  active: "main",
  audio: [],
};

/** Ce qu'il faut retenir de l'état courant. Pure : c'est ce qui la rend prouvable. */
export function toSession(
  scenes: SceneInfo[],
  active: string,
  audio: AudioSourceInfo[] = [],
  /** Les réglages de texte, par scène puis par source. Portés par l'application : elle est
   * leur seul auteur, le moteur ne fait que les appliquer. */
  textSettings: Record<string, Record<string, TextSettings>> = {},
): SessionDoc {
  return {
    active,
    scenes: scenes.map((scene) => ({
      name: scene.name,
      // La caméra est retenue à part : elle se recrée par sa propre commande, jamais comme
      // une capture — la poser deux fois ouvrirait l'appareil une seconde fois.
      cameras: camerasIn(scene),
      sources: scene.sources
        .filter((source) => source.source_kind !== "camera")
        .map((source) => ({
          name: source.name,
          kind: source.source_kind,
          targetId: source.target_id,
          text: textSettings[scene.name]?.[source.name],
          x: source.x,
          y: source.y,
          scalePercent: source.scale_percent,
          locked: source.locked,
        })),
    })),
    audio: audio.map((entry) => ({
      name: entry.name,
      kind: entry.kind,
      deviceId: entry.device_id,
      volumePercent: entry.volume_percent,
      monitorVolumePercent: entry.monitor_volume_percent,
      muted: entry.muted,
      monitoring: entry.monitoring,
      noiseSuppression: entry.noise_suppression,
      noiseMethod: entry.noise_method,
      noiseLevelDb: entry.noise_level_db,
    })),
  };
}

function camerasIn(scene: SceneInfo): SavedCamera[] {
  return scene.sources
    .filter((source) => source.source_kind === "camera")
    .map((camera) => ({
      deviceId: camera.target_id,
      name: camera.name,
      // Les filtres appartiennent à la caméra depuis le 2026-09-06 : deux caméras d'une
      // même scène peuvent avoir deux allures, qu'un réglage par scène ne saurait dire.
      backgroundRemoval: camera.background_removal,
      maskShape: camera.mask_shape,
      x: camera.x,
      y: camera.y,
      scalePercent: camera.scale_percent,
      locked: camera.locked,
    }));
}

/** Une étape du rejeu. Volontairement décrite en données et non en appels : la liste est
 * ainsi vérifiable par un test, sans moteur ni écran. */
export type ReplayStep =
  | { do: "createScene"; scene: string }
  | {
      do: "addSource";
      scene: string;
      kind: SourceKind;
      targetId: string;
      name: string;
    }
  | {
      do: "transform";
      scene: string;
      name: string;
      x: number;
      y: number;
      scalePercent: number;
    }
  | { do: "addCamera"; scene: string; deviceId: string }
  | {
      do: "cameraFilters";
      scene: string;
      deviceId: string;
      background: boolean;
      mask: MaskShape;
    }
  | { do: "addAudio"; audio: SavedAudio }
  | { do: "lock"; scene: string; name: string }
  | {
      /** Rejoue l'apparence d'une source texte. Après son ajout, jamais avant : le moteur
       * n'a rien à régler tant que la source n'existe pas. */
      do: "textSettings";
      scene: string;
      name: string;
      settings: TextSettings;
    }
  | { do: "switchScene"; scene: string };

/** Le plan pour retrouver l'état sauvegardé, à partir de ce que le moteur a DÉJÀ.
 *
 * Ordre imposé : créer les scènes manquantes, puis y ajouter les sources manquantes, puis
 * replacer TOUTES les sources, et seulement à la fin revenir sur la scène active. Basculer
 * en dernier évite de diffuser une scène à moitié construite.
 */
export function buildReplay(
  saved: SessionDoc,
  current: SceneInfo[],
): ReplayStep[] {
  const currentByName = new Map(current.map((scene) => [scene.name, scene]));
  const steps: ReplayStep[] = [];

  for (const scene of saved.scenes) {
    if (!currentByName.has(scene.name)) {
      steps.push({ do: "createScene", scene: scene.name });
    }
  }

  for (const scene of saved.scenes) {
    const existing = new Set(
      (currentByName.get(scene.name)?.sources ?? []).map((s) => s.name),
    );
    for (const source of scene.sources) {
      if (existing.has(source.name)) continue;
      steps.push({
        do: "addSource",
        scene: scene.name,
        kind: source.kind,
        targetId: source.targetId,
        name: source.name,
      });
    }
  }

  // L'apparence des textes se rejoue APRÈS leur ajout, et pour TOUTES les sources retenues
  // — y compris celles qui existaient déjà dans le moteur. Ne la reposer que sur les
  // nouvelles laisserait une source rejouée deux fois de suite avec l'apparence de la
  // première session seulement.
  for (const scene of saved.scenes) {
    for (const source of scene.sources) {
      if (source.kind !== "text" || !source.text) continue;
      steps.push({
        do: "textSettings",
        scene: scene.name,
        name: source.name,
        settings: source.text,
      });
    }
  }

  // La caméra vient APRÈS les captures : elle est une source physique unique, et l'ajouter
  // scène par scène réutilise le même appareil au lieu de le rouvrir.
  for (const scene of saved.scenes) {
    const live = currentByName.get(scene.name);
    for (const camera of camerasOf(scene)) {
      const already = live?.sources.some(
        (source) =>
          source.source_kind === "camera" &&
          source.target_id === camera.deviceId,
      );
      if (!already) {
        steps.push({
          do: "addCamera",
          scene: scene.name,
          deviceId: camera.deviceId,
        });
      }
      steps.push({
        do: "cameraFilters",
        scene: scene.name,
        deviceId: camera.deviceId,
        background: camera.backgroundRemoval,
        mask: maskShapeOf(camera),
      });
    }
  }

  // Le placement est réappliqué même sur une source déjà présente : la capture d'écran que
  // le moteur pose lui-même au démarrage arrive au cadre par défaut, pas là où l'utilisateur
  // l'avait mise. La caméra en fait partie — elle vient d'être ajoutée juste au-dessus, donc
  // au cadre par défaut elle aussi, et c'est ici et nulle part ailleurs qu'elle retrouve le
  // sien (Jay, 2026-08-06 : le cadrage était écrit sur le disque, jamais rendu à l'écran).
  for (const scene of saved.scenes) {
    for (const source of scene.sources) {
      steps.push({
        do: "transform",
        scene: scene.name,
        name: source.name,
        x: source.x,
        y: source.y,
        scalePercent: source.scalePercent,
      });
    }
    for (const camera of camerasOf(scene)) {
      steps.push({
        do: "transform",
        scene: scene.name,
        name: camera.name ?? DEFAULT_CAMERA_NAME,
        x: camera.x,
        y: camera.y,
        scalePercent: camera.scalePercent,
      });
    }
  }

  // Les verrous se posent APRÈS tous les placements, jamais avant : une source verrouillée
  // trop tôt serait figée au cadre par défaut, et le cadrage retenu perdu pour de bon.
  for (const scene of saved.scenes) {
    for (const source of scene.sources) {
      if (source.locked) {
        steps.push({ do: "lock", scene: scene.name, name: source.name });
      }
    }
    for (const camera of camerasOf(scene)) {
      if (camera.locked) {
        steps.push({
          do: "lock",
          scene: scene.name,
          name: camera.name ?? DEFAULT_CAMERA_NAME,
        });
      }
    }
  }

  // Le mixeur est indépendant des scènes (canaux globaux) : il se rejoue à part, et son
  // ordre n'a pas d'importance vis-à-vis d'elles.
  for (const entry of saved.audio) {
    steps.push({ do: "addAudio", audio: entry });
  }

  if (saved.active) {
    steps.push({ do: "switchScene", scene: saved.active });
  }
  return steps;
}
