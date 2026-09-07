// L'espace entre les cartes du cockpit, selon la densité choisie.
//
// POURQUOI ce n'est pas du CSS : le composant de panneaux positionne ses cartes lui-même et
// reçoit l'écart en OPTION (`gap: 10`). Une feuille de style ne peut pas l'atteindre — s'y
// essayer produit une marge qui S'AJOUTE à la taille imposée, chaque carte déborde, et une
// barre de défilement apparaît partout (vécu le 2026-09-05).
//
// Ce que ce module NE fait pas : étirer les 106 espacements internes du code. Un réglage
// qui déplace tout d'un coup n'est pas réglable — Jay ne pourrait pas dire ce qui a bougé,
// et la mise en page qu'il vient de valider partirait avec.

import type { useMorphicDensity } from "@theermite/morphic-adapter";

/** Le choix de densité, tel que le module le rend (`null` = aucun choix fait). */
type DensityChoice = ReturnType<typeof useMorphicDensity>[0];

/** L'écart validé par Jay le 2026-09-05, celui de la maquette. C'est le point de repos :
 * tant que personne ne demande autre chose, la mise en page ne bouge pas. */
export const BASE_GAP = 10;

/** L'écart en pixels pour une densité donnée.
 *
 * Aucun choix rend l'écart validé, et non « compact » : une absence de préférence n'est pas
 * une préférence pour le serré. Une valeur inconnue — une version future du module qui
 * ajouterait un cran — retombe aussi sur l'écart validé plutôt que de casser l'écran.
 *
 * Le plancher n'est jamais nul : un écart nul recolle les cartes et efface le fond qui les
 * détache les unes des autres, ce qui est justement ce que Jay avait demandé de corriger. */
export function gapForDensity(choice: DensityChoice): number {
  switch (choice) {
    case "compact":
      return 4;
    case "spacious":
      return 20;
    default:
      return BASE_GAP;
  }
}
