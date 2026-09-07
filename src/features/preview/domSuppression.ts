// Retirer l'aperçu quand une fenêtre surgissante qu'on ne contrôle PAS s'ouvre.
//
// POURQUOI ce module existe en plus de `suppression.ts` : nos propres fenêtres surgissantes
// appellent `suppressPreview()` elles-mêmes, parce qu'on écrit leur code. Le panneau
// d'adaptation vient du module `@theermite/morphic-adapter`, et sa version 2.0.0-beta.1
// n'expose aucun signal d'ouverture — impossible de lui demander de s'annoncer.
//
// Alors on regarde s'il EST là, plutôt que d'écouter ce qui l'ouvre. C'est la différence
// entre observer un état et deviner une cause : écouter les clics raterait la fermeture au
// clavier, la fermeture par clic à côté, et tout chemin que le module ajouterait demain.
//
// Vécu le 2026-09-07 : le panneau s'ouvrait, et l'aperçu se dessinait par-dessus. Une
// fenêtre native passe toujours devant le web, quel que soit l'empilement — voir
// `suppression.ts` pour le fond du sujet.

import { suppressPreview } from "./suppression";

/** Surveille l'apparition d'un élément et retire l'aperçu tant qu'il est là.
 *
 * Rend la fonction qui arrête la surveillance ET relâche la demande en cours — sans ce
 * relâchement, démonter le cockpit pendant que le panneau est ouvert laisserait l'aperçu
 * caché pour toujours.
 *
 * Une seule demande est tenue à la fois, quel que soit le nombre de mutations observées :
 * chaque passage en prendrait une de plus, le compteur ne retomberait jamais à zéro, et
 * l'aperçu ne reviendrait plus. */
export function watchForOverlay(
  selector: string,
  root: Document = document,
): () => void {
  let release: (() => void) | null = null;

  const sync = () => {
    const present = root.querySelector(selector) !== null;
    if (present && release === null) {
      release = suppressPreview();
      return;
    }
    if (!present && release !== null) {
      release();
      release = null;
    }
  };

  // L'état d'AVANT compte autant que les changements : un rechargement de page pendant que
  // le panneau est ouvert ne produit aucune mutation, et l'aperçu resterait devant lui.
  sync();

  const observer = new MutationObserver(sync);
  observer.observe(root.body, { childList: true, subtree: true });

  return () => {
    observer.disconnect();
    release?.();
    release = null;
  };
}
