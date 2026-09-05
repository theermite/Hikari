// La vignette d'une scène, telle que la maquette la dessine à gauche de chaque ligne.
//
// Ce qu'elle N'EST PAS : une image de ce que la scène montre. Le moteur ne rend aucune
// miniature aujourd'hui, et en dessiner une fausse serait pire que de ne rien montrer —
// l'utilisateur croirait voir sa scène (Dignity : jamais faire semblant qu'une chose
// existe).
//
// Ce qu'elle est : un repère visuel honnête. Le pictogramme de ce que la scène contient
// principalement — la caméra si elle en a une, sinon sa première source. À défaut, un
// cadre vide qui dit « scène vide » plutôt que de mentir.

import { SOURCE_ICON } from "./ScenesControls";
import type { SceneInfo } from "./types";

/** Le pictogramme représentatif d'une scène, ou `null` si elle est vide. */
export function thumbIcon(scene: SceneInfo): string | null {
  if (scene.has_camera) return "🎥";
  const first = scene.sources[0];
  if (!first) return null;
  return SOURCE_ICON[first.kind] ?? "▪";
}

interface SceneThumbProps {
  scene: SceneInfo;
  live: boolean;
}

export function SceneThumb({ scene, live }: SceneThumbProps) {
  const icon = thumbIcon(scene);
  return (
    <span
      aria-hidden="true"
      className={`flex h-9 w-14 shrink-0 items-center justify-center rounded-[5px] border text-[15px] ${
        live
          ? "border-hikari-accent/50 bg-hikari-accent/10"
          : "border-hikari-line bg-hikari-bg"
      }`}
    >
      {icon ?? <span className="text-[10px] text-hikari-txt-faint">vide</span>}
    </span>
  );
}
