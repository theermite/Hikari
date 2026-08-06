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
import type { SceneInfo, SourceKind } from "./types";

/** Une source telle qu'on la retrouvera au prochain lancement. */
export interface SavedSource {
  name: string;
  kind: SourceKind;
  targetId: string;
  x: number;
  y: number;
  scalePercent: number;
}

export interface SavedScene {
  name: string;
  sources: SavedSource[];
  camera?: SavedCamera;
}

/** La caméra d'une scène : le même appareil partout, mais un cadrage et des filtres propres
 * à chaque scène — c'est exactement le flux que Jay utilise. */
export interface SavedCamera {
  deviceId: string;
  /** Le nom que le moteur donne à la source caméra. Retenu parce que replacer un objet
   * exige de savoir le nommer — sans lui, le cadrage ci-dessous ne serait adressable par
   * aucune commande au rejeu. Absent des sessions écrites avant le 2026-08-06. */
  name?: string;
  backgroundRemoval: boolean;
  circleMask: boolean;
  x: number;
  y: number;
  scalePercent: number;
}

/** Le nom que le moteur donne à sa caméra quand une session ancienne ne le porte pas
 * (`CAMERA_SOURCE_NAME`, `crates/protocol/src/lib.rs` — une seule caméra, donc un seul nom
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
): SessionDoc {
  return {
    active,
    scenes: scenes.map((scene) => ({
      name: scene.name,
      // La caméra est retenue à part : elle se recrée par sa propre commande, jamais comme
      // une capture — la poser deux fois ouvrirait l'appareil une seconde fois.
      camera: cameraOf(scene),
      sources: scene.sources
        .filter((source) => source.source_kind !== "camera")
        .map((source) => ({
          name: source.name,
          kind: source.source_kind,
          targetId: source.target_id,
          x: source.x,
          y: source.y,
          scalePercent: source.scale_percent,
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

function cameraOf(scene: SceneInfo): SavedCamera | undefined {
  const camera = scene.sources.find((s) => s.source_kind === "camera");
  if (!camera) return undefined;
  return {
    deviceId: camera.target_id,
    name: camera.name,
    backgroundRemoval: scene.background_removal,
    circleMask: scene.circle_mask,
    x: camera.x,
    y: camera.y,
    scalePercent: camera.scale_percent,
  };
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
  | { do: "cameraFilters"; scene: string; background: boolean; circle: boolean }
  | { do: "addAudio"; audio: SavedAudio }
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

  // La caméra vient APRÈS les captures : elle est une source physique unique, et l'ajouter
  // scène par scène réutilise le même appareil au lieu de le rouvrir.
  for (const scene of saved.scenes) {
    if (!scene.camera) continue;
    const already = currentByName
      .get(scene.name)
      ?.sources.some((s) => s.source_kind === "camera");
    if (!already) {
      steps.push({
        do: "addCamera",
        scene: scene.name,
        deviceId: scene.camera.deviceId,
      });
    }
    steps.push({
      do: "cameraFilters",
      scene: scene.name,
      background: scene.camera.backgroundRemoval,
      circle: scene.camera.circleMask,
    });
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
    if (scene.camera) {
      steps.push({
        do: "transform",
        scene: scene.name,
        name: scene.camera.name ?? DEFAULT_CAMERA_NAME,
        x: scene.camera.x,
        y: scene.camera.y,
        scalePercent: scene.camera.scalePercent,
      });
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
