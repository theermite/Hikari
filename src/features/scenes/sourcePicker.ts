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
  /** Un fichier se choisit sur le disque, le reste se choisit dans une liste — sauf le
   * texte, qui ne se choisit pas du tout : il s'écrit. */
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
    // Une caméra est une source ordinaire depuis le 2026-09-06 (Jay). Avant, elle
    // s'ajoutait depuis un panneau à part : deux portes d'entrée pour un même geste, et
    // les réglages d'une caméra posée devenaient inatteignables dès que ce panneau
    // perdait le fil.
    kind: "camera",
    label: "Une caméra",
    hint: "Une webcam branchée sur cette machine.",
    isFile: false,
  },
  {
    // La seule famille dont le contenu vient de l'UTILISATEUR et non de la machine : ni
    // liste à parcourir, ni fichier à choisir. On l'écrit, et c'est pour ça qu'elle a son
    // propre chemin dans la fenêtre d'ajout.
    kind: "text",
    label: "Du texte",
    hint: "Un titre, un pseudo, un message d'attente — écrit à l'écran.",
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

/** Tout ce qu'une scène peut recevoir, tel que la machine le rapporte à cet instant.
 *
 * Vit ici plutôt que dans la fenêtre d'ajout : c'est une donnée, pas un morceau
 * d'affichage, et les fonctions pures ci-dessous la lisent sans toucher au DOM. */
export interface CaptureTargets {
  games: CaptureTarget[];
  windows: CaptureTarget[];
  monitors: CaptureTarget[];
  cameras: CaptureTarget[];
}

/** Ce que chaque famille vivante propose. Les familles de fichier n'ont pas de liste : on
 * y ouvre le sélecteur du système. */
export function targetsFor(
  kind: SourceKind,
  targets: CaptureTargets,
): CaptureTarget[] {
  if (kind === "game") return targets.games;
  if (kind === "window") return targets.windows;
  if (kind === "monitor") return targets.monitors;
  if (kind === "camera") return targets.cameras;
  return [];
}

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
export function searchAll(targets: CaptureTargets, query: string): SearchHit[] {
  const families: [SourceKind, CaptureTarget[]][] = [
    ["game", targets.games],
    ["window", targets.windows],
    ["monitor", targets.monitors],
    ["camera", targets.cameras],
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
