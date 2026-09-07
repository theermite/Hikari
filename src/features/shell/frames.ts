// Le taux d'images perdues, et ce qu'il faut en dire.
//
// Le moteur envoie déjà `dropped` ET `total` ; seul `dropped` était affiché. Le seuil de
// Jay est pourtant un taux — « moins de 2 % » — donc un compte brut ne lui permet pas de
// décider en direct. Il a dû me donner le nombre pour que je fasse la division.
//
// Ce que ce compteur mesure : les images que le RÉSEAU n'a pas pu envoyer
// (`obs_output_get_frames_dropped`). Ce n'est pas un problème d'encodage ni de machine.

/** Le seuil de Jay, exprimé par lui le 2026-09-07 : « moins de 2 %, c'était ton chiffre ».
 *
 * C'est la SEULE valeur d'origine externe ici. Le palier intermédiaire en dessous est
 * calculé à partir d'elle (sa moitié) et non repris ailleurs : un seuil inventé produit
 * une fausse alarme ou une fausse assurance, et les deux coûtent plus cher que pas de
 * seuil du tout. */
const SEUIL_JAY_POURCENT = 2;

/** La moitié du seuil de Jay — dérivée, jamais trouvée dans une source. Elle existe pour
 * qu'il voie la dégradation ARRIVER plutôt que de la découvrir une fois franchie. */
const SEUIL_ATTENTION_POURCENT = SEUIL_JAY_POURCENT / 2;

export type DropVerdict = "ok" | "attention" | "critique";

/** La part d'images perdues, en pourcentage, ou `null` quand il n'y a rien à mesurer.
 *
 * `null` et non `0` sur un total nul : zéro image envoyée n'est pas zéro perte, c'est une
 * absence de mesure. Les confondre affiche « 0 % » au démarrage d'un direct et donne une
 * assurance que rien ne soutient — même famille que les trois états de la carte
 * Préparation, où « on ne sait pas » est distinct de « c'est bon ». */
export function dropRate(dropped: number, total: number): number | null {
  if (!Number.isFinite(total) || total <= 0) return null;
  if (!Number.isFinite(dropped) || dropped < 0) return null;
  return (dropped / total) * 100;
}

/** Ce qu'il faut dire du taux. `null` en entrée rend `null` : pas de mesure, pas de verdict. */
export function dropVerdict(rate: number | null): DropVerdict | null {
  if (rate === null) return null;
  if (rate >= SEUIL_JAY_POURCENT) return "critique";
  if (rate >= SEUIL_ATTENTION_POURCENT) return "attention";
  return "ok";
}
