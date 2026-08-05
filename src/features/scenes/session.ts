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
}

export interface SessionDoc {
  scenes: SavedScene[];
  active: string;
}

export const EMPTY_SESSION: SessionDoc = { scenes: [], active: "main" };

/** La caméra ne se rejoue pas par ce chemin : c'est UNE source physique partagée entre
 * scènes, recréée par sa propre commande. La retenir ici la ferait recréer en double. */
const CAMERA_KIND = "dshow_input";

/** Ce qu'il faut retenir de l'état courant. Pure : c'est ce qui la rend prouvable. */
export function toSession(scenes: SceneInfo[], active: string): SessionDoc {
  return {
    active,
    scenes: scenes.map((scene) => ({
      name: scene.name,
      sources: scene.sources
        .filter((source) => source.kind !== CAMERA_KIND)
        .map((source) => ({
          name: source.name,
          kind: source.source_kind,
          targetId: source.target_id,
          x: source.x,
          y: source.y,
          scalePercent: source.scale_percent,
        })),
    })),
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

  // Le placement est réappliqué même sur une source déjà présente : la capture d'écran que
  // le moteur pose lui-même au démarrage arrive au cadre par défaut, pas là où l'utilisateur
  // l'avait mise.
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
  }

  if (saved.active) {
    steps.push({ do: "switchScene", scene: saved.active });
  }
  return steps;
}
