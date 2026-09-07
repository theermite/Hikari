// Où un panneau qui s'ouvre vers l'extérieur a le droit de vivre.
//
// Né d'un défaut coûteux (Jay, 2026-09-07) : le bouton d'adaptation « n'ouvre absolument
// rien, il est juste là, en décoration ». Il ouvrait bien son panneau. Celui-ci se dessine
// SOUS le bouton, donc hors de la carte de la barre du haut — et cette carte coupe ce qui
// dépasse, pour tenir ses coins arrondis. Le panneau était découpé à chaque ouverture,
// sans une erreur, sans une trace.
//
// Le coût réel n'est pas le panneau invisible : c'est qu'un composant qui marche a été
// pris pour un composant décoratif. C'est exactement le mauvais diagnostic contre lequel
// la règle du module morphique existe.

/** Les façons de couper ce qui dépasse. Liste fermée, tirée des classes utilitaires
 * réellement disponibles — `overflow-visible` contient le mot sans rien couper, d'où la
 * comparaison sur des classes entières et jamais sur un fragment. */
const CLASSES_QUI_COUPENT = new Set([
  "overflow-hidden",
  "overflow-clip",
  "overflow-x-hidden",
  "overflow-y-hidden",
  "overflow-x-clip",
  "overflow-y-clip",
]);

/** Ce conteneur découpe-t-il ce qui dépasse de lui ? */
export function clipsItsOverflow(className: string): boolean {
  return className
    .split(/\s+/)
    .some((classe) => CLASSES_QUI_COUPENT.has(classe));
}

/** Un élément qui s'ouvre vers l'extérieur échappe-t-il à tout découpage ?
 *
 * `ancestors` va du parent immédiat vers la racine. Un SEUL ancêtre qui coupe suffit à
 * rendre le panneau invisible — c'est pourquoi la réponse est « tous », jamais « le
 * premier ». */
export function escapesClipping(ancestors: readonly string[]): boolean {
  return !ancestors.some(clipsItsOverflow);
}
