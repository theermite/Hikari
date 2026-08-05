// Masquage temporaire de l'aperçu (B1b + B6).
//
// POURQUOI ce module existe : l'aperçu n'est PAS de la page web. C'est la fenêtre native du
// moteur, greffée dans la fenêtre de l'app (ADR-013). Une fenêtre native se dessine toujours
// AU-DESSUS du contenu web, quel que soit l'empilement CSS — même la couche supérieure d'une
// modale native reste dessous. Vécu le 2026-08-05 : la fenêtre de réglages audio s'ouvrait
// derrière l'aperçu, donc invisible.
//
// La seule parade est de retirer l'aperçu de l'écran pendant qu'un élément web doit passer
// devant. Ce module tient ce comptage, et il est PARTAGÉ : deux demandeurs simultanés ne
// doivent pas se marcher dessus, le dernier qui relâche décide.

type Listener = (suppressed: boolean) => void;

let holders = 0;
const listeners = new Set<Listener>();

function notify(): void {
  const suppressed = holders > 0;
  for (const listener of listeners) listener(suppressed);
}

/** Demande le masquage de l'aperçu et rend la fonction qui relâche CETTE demande.
 * Comptage de références : relâcher une demande ne réaffiche l'aperçu que si plus personne
 * ne le masque. La fonction rendue est idempotente — l'appeler deux fois ne décompte qu'une
 * fois, sinon un démontage React en double réafficherait l'aperçu sous une modale ouverte. */
export function suppressPreview(): () => void {
  holders += 1;
  notify();
  let released = false;
  return () => {
    if (released) return;
    released = true;
    holders = Math.max(0, holders - 1);
    notify();
  };
}

/** Si l'aperçu doit rester masqué en ce moment. */
export function isPreviewSuppressed(): boolean {
  return holders > 0;
}

/** S'abonne aux changements. Rend la fonction de désabonnement. */
export function onPreviewSuppressionChange(listener: Listener): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

/** Remet le compteur à zéro — réservé aux tests, pour qu'un cas ne fuite pas sur le suivant. */
export function resetPreviewSuppression(): void {
  holders = 0;
  listeners.clear();
}
