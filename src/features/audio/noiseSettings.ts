// Réglages anti-bruit et résumé d'une ligne du mixeur (B6) — logique pure, prouvée sans DOM.
//
// Le vocabulaire à l'écran parle de FORCE (0 à 100), pas de décibels : le moteur attend une
// intensité en décibels où -60 est le plus fort et 0 le plus faible — une échelle inversée
// que personne ne devine. La conversion vit ici, testée, plutôt que dispersée dans le JSX.

import type { NoiseMethod } from "./types";

/** Bornes de l'intensité côté moteur (source obs-filters, vérifiée 2026-08-04). */
export const NOISE_LEVEL_MIN_DB = -60;
export const NOISE_LEVEL_MAX_DB = 0;

/** Les deux méthodes, dites par ce qu'elles FONT plutôt que par leur nom technique. Le nom
 * technique reste disponible au survol : un streamer qui sait ce qu'est RNNoise ne doit pas
 * se sentir pris pour un débutant, et un novice ne doit pas avoir à le connaître. */
export const NOISE_METHODS: {
  value: NoiseMethod;
  label: string;
  hint: string;
}[] = [
  {
    value: "speex",
    label: "Léger",
    hint: "Speex — réglable, très peu gourmand.",
  },
  {
    value: "rnnoise",
    label: "Fort",
    hint: "RNNoise — plus propre, aucun réglage, plus gourmand.",
  },
];

/** Si cette méthode expose une force à régler. Seul « Léger » en a une : afficher un curseur
 * pour l'autre serait inventer un réglage qui n'existe pas dans le moteur. */
export function hasLevel(method: NoiseMethod): boolean {
  return method === "speex";
}

/** Décibels du moteur → force lisible (0 à 100). L'échelle du moteur est inversée : -60 dB
 * est la suppression la PLUS forte. */
export function levelToStrength(levelDb: number): number {
  if (!Number.isFinite(levelDb)) return 0;
  const clamped = Math.min(
    NOISE_LEVEL_MAX_DB,
    Math.max(NOISE_LEVEL_MIN_DB, levelDb),
  );
  const strength = Math.round((clamped / NOISE_LEVEL_MIN_DB) * 100);
  // `0 / -60` vaut `-0` en JavaScript, une valeur distincte de `0` pour une comparaison
  // stricte. Sans cette normalisation, une force nulle voyagerait en `-0` et toute
  // comparaison d'égalité la rejetterait sans qu'on voie pourquoi.
  return strength === 0 ? 0 : strength;
}

/** Force lisible (0 à 100) → décibels du moteur. Réciproque exacte de `levelToStrength`. */
export function strengthToLevel(strength: number): number {
  const clamped = Math.min(100, Math.max(0, strength));
  return (clamped / 100) * NOISE_LEVEL_MIN_DB;
}
