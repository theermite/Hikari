// Choix d'une source à ajouter (brique Sources, tranche 2) — logique pure, prouvée sans DOM.
//
// Deux familles de questions, pas une : un jeu, une fenêtre ou un écran se CHOISIT dans une
// liste de ce qui tourne ; une image ou une vidéo se CHOISIT sur le disque. Le panneau doit
// donc poser deux questions différentes, et cette distinction vit ici plutôt que dispersée
// dans le JSX.

import type { CaptureTarget, SourceKind } from "./types";

/** Les familles proposées à l'ajout, dites par ce qu'elles montrent. */
export interface SourceFamily {
  kind: SourceKind;
  label: string;
  hint: string;
  /** Un fichier se choisit sur le disque, le reste se choisit dans une liste. */
  isFile: boolean;
}

export const SOURCE_FAMILIES: SourceFamily[] = [
  {
    kind: "game",
    label: "Un jeu",
    hint: "Accroche le jeu directement — la voie la plus fluide.",
    isFile: false,
  },
  {
    kind: "window",
    label: "Une fenêtre",
    hint: "N'importe quelle fenêtre ouverte, même hors jeu.",
    isFile: false,
  },
  {
    kind: "monitor",
    label: "Un écran",
    hint: "Tout un écran, choisi parmi les tiens.",
    isFile: false,
  },
  {
    kind: "image",
    label: "Une image",
    hint: "Logo, habillage, écran d'attente.",
    isFile: true,
  },
  {
    kind: "video",
    label: "Une vidéo",
    hint: "Lue en boucle.",
    isFile: true,
  },
];

/** Les extensions proposées par le sélecteur de fichiers, par famille. */
export const FILE_FILTERS: Record<string, string[]> = {
  image: ["png", "jpg", "jpeg", "gif", "webp", "bmp"],
  video: ["mp4", "mkv", "mov", "webm", "avi", "gif"],
};

/** Enlève accents et casse pour comparer ce que l'utilisateur TAPE à ce qu'il LIT.
 * Sans ça, chercher « ecran » ne trouverait jamais « Écran 1 ». */
function fold(text: string): string {
  return text
    .normalize("NFD")
    .replace(/\p{Diacritic}/gu, "")
    .toLowerCase();
}

/** Si une cible correspond à la recherche. Une recherche vide accepte tout — un champ vide
 * ne doit jamais masquer la liste. */
export function matchesSearch(target: CaptureTarget, query: string): boolean {
  const needle = fold(query.trim());
  if (!needle) return true;
  // Tous les mots doivent apparaître, dans n'importe quel ordre : « chrome doc » trouve
  // « Document — Google Chrome », ce qu'une recherche de la phrase entière raterait.
  return needle.split(/\s+/).every((word) => fold(target.label).includes(word));
}

/** Le nom donné au fichier une fois posé dans la scène : son nom, sans le chemin ni
 * l'extension. C'est ce que l'utilisateur reconnaît. */
export function nameFromPath(path: string): string {
  const file = path.split(/[\\/]/).pop() ?? path;
  const dot = file.lastIndexOf(".");
  return dot > 0 ? file.slice(0, dot) : file;
}
