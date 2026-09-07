// Les réglages d'une source texte, côté interface.
//
// Jay, 2026-09-07 : « mettre une source de texte sans réglage, sans personnalisation, je
// trouve ça très inutile ». Le greffon du moteur porte tout cela depuis toujours ; rien ne
// l'atteignait. Ce fichier tient les valeurs de départ et les bornes — la partie qui décide,
// donc la partie qui se teste.

/** Une couleur telle que l'utilisateur la choisit. Le moteur la convertit lui-même : son
 * ordre d'octets est une convention interne, et la faire voyager ici créerait deux endroits
 * qui pensent la couleur différemment. */
export interface Rgb {
  r: number;
  g: number;
  b: number;
}

export type TextAlign = "left" | "center" | "right";

export interface TextSettings {
  face: string;
  size: number;
  bold: boolean;
  italic: boolean;
  color: Rgb;
  outline: boolean;
  outline_size: number;
  outline_color: Rgb;
  align: TextAlign;
}

/** Ce qu'on pose sur un texte que personne n'a encore réglé.
 *
 * Blanc, gros, et AVEC contour noir. Le contour n'est pas un ornement : c'est ce qui rend le
 * texte lisible sur une scène claire comme sur une scène sombre. Sans lui, le premier essai
 * de Jay sur un fond clair montrerait un texte invisible — et un premier essai raté ne
 * donne pas envie du second. */
export const DEFAULT_TEXT_SETTINGS: TextSettings = {
  face: "Inter",
  size: 48,
  bold: true,
  italic: false,
  color: { r: 255, g: 255, b: 255 },
  outline: true,
  outline_size: 4,
  outline_color: { r: 0, g: 0, b: 0 },
  align: "left",
};

/** Complète un enregistrement partiel ou absent.
 *
 * Une source texte posée AVANT ce jour n'a aucun réglage enregistré, et une session écrite
 * par une version plus ancienne peut n'en porter qu'une partie. Lire sans valeur de repli
 * afficherait des champs vides et poserait une police nommée « » — la même famille que le
 * champ ajouté à une donnée persistée sans défaut au moment de la lecture. */
export function withDefaults(
  settings: Partial<TextSettings> | undefined,
): TextSettings {
  return { ...DEFAULT_TEXT_SETTINGS, ...(settings ?? {}) };
}

/** Une taille de texte utilisable.
 *
 * Le plancher n'est jamais zéro : un texte de taille nulle est invisible, et l'utilisateur
 * le chercherait dans sa scène sans jamais le voir — c'est le défaut que le refus du texte
 * vide évite déjà au moment de l'ajout. Le plafond évite qu'un chiffre tapé de travers
 * remplisse la scène entière. */
export function clampFontSize(size: number): number {
  if (!Number.isFinite(size)) return DEFAULT_TEXT_SETTINGS.size;
  return Math.min(500, Math.max(8, Math.round(size)));
}

/** Une épaisseur de contour utilisable. Zéro est légitime — c'est « pas de contour », un
 * choix, au contraire d'un texte de taille nulle qui est une disparition. */
export function clampOutlineSize(size: number): number {
  if (!Number.isFinite(size)) return DEFAULT_TEXT_SETTINGS.outline_size;
  return Math.min(50, Math.max(0, Math.round(size)));
}
