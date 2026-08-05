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
export function fold(text: string): string {
  return (
    text
      .normalize("NFD")
      // Plage explicite des marques combinantes, PAS `\p{Diacritic}` : cette classe Unicode
      // vidait la chaîne entière dans le navigateur de l'app (vécu 2026-08-05 — le filtre
      // laissait tout passer, une recherche vide acceptant tout), alors qu'elle se comportait
      // normalement dans le lanceur de tests. Une plage de codes est supportée partout de la
      // même façon, et elle couvre exactement les accents latins qui nous concernent.
      .replace(/[̀-ͯ]/g, "")
      .toLowerCase()
  );
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

/** Retire les cibles en double d'une liste.
 *
 * POURQUOI (vécu 2026-08-05) : Windows expose la même application plusieurs fois — douze
 * « Spotify Widget » portant le MÊME identifiant dans la liste des jeux. Douze lignes
 * identiques n'aident personne à choisir, et surtout elles cassaient l'affichage : leur
 * identifiant servait de clé de rendu, et des clés en double empêchaient React de savoir
 * quelle ligne remplacer — la liste restait figée pendant la frappe.
 */
export function dedupeTargets(targets: CaptureTarget[]): CaptureTarget[] {
  const seen = new Set<string>();
  return targets.filter((target) => {
    // Deux entrées qui portent le même nom ET le même identifiant sont la même chose.
    const key = `${target.id}|${target.label}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

/** Un résultat de recherche : la cible, et la famille dont elle vient. */
export interface SearchHit {
  kind: SourceKind;
  target: CaptureTarget;
}

/** Cherche dans TOUTES les familles vivantes à la fois.
 *
 * POURQUOI global et non dans la famille choisie (correction 2026-08-05) : quelqu'un qui
 * tape un nom cherche CETTE chose, pas « cette chose parmi les jeux ». Restreindre à la
 * famille ouverte donnait une liste vide sans rien expliquer — Jay cherchait une fenêtre
 * depuis l'onglet « Un jeu ».
 */
export function searchAll(
  games: CaptureTarget[],
  windows: CaptureTarget[],
  monitors: CaptureTarget[],
  query: string,
): SearchHit[] {
  const families: [SourceKind, CaptureTarget[]][] = [
    ["game", games],
    ["window", windows],
    ["monitor", monitors],
  ];
  const seen = new Set<string>();
  return families.flatMap(([kind, list]) =>
    list
      .filter((target) => matchesSearch(target, query))
      // Une même fenêtre apparaît souvent dans « jeux » ET dans « fenêtres ». La montrer
      // deux fois ferait douter du résultat ; la première famille gagne.
      .filter((target) => {
        if (seen.has(target.id)) return false;
        seen.add(target.id);
        return true;
      })
      .map((target) => ({ kind, target })),
  );
}

/** Le nom donné au fichier une fois posé dans la scène : son nom, sans le chemin ni
 * l'extension. C'est ce que l'utilisateur reconnaît. */
export function nameFromPath(path: string): string {
  const file = path.split(/[\\/]/).pop() ?? path;
  const dot = file.lastIndexOf(".");
  return dot > 0 ? file.slice(0, dot) : file;
}
