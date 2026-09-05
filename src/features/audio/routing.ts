// Le routage d'une piste audio, dit comme la maquette le montre : deux interrupteurs,
// « Écoute » et « Diffusé ».
//
// Ce que ça remplace : une phrase d'état (« Public seul ») et un réglage caché derrière un
// engrenage. Jay, 2026-09-05 : « la manière dont il est fait n'est pas optimisée ni
// intuitive ». Une phrase se lit, elle ne se manipule pas — pour changer la destination du
// son il fallait ouvrir une fenêtre.
//
// Sous le capot, libobs n'expose pas deux interrupteurs mais UN réglage à trois valeurs.
// Ce module fait la traduction dans les deux sens, et c'est tout ce qu'il fait : pur,
// donc éprouvé sans moteur ni écran.

import type { AudioMonitoring } from "./types";

/** Ce que l'utilisateur voit : deux cases, indépendantes en apparence. */
export interface AudioRouting {
  /** Le son part dans le casque du streamer. */
  listen: boolean;
  /** Le son part vers le direct, donc vers le public. */
  broadcast: boolean;
}

/** Traduit le réglage du moteur en deux cases.
 *
 * `none` ne veut PAS dire « aucune sortie » : dans libobs, c'est « pas de retour casque »,
 * et le son continue d'aller au direct. Le contre-sens serait facile et coûterait cher —
 * l'utilisateur croirait avoir coupé une piste qui s'entend encore à l'antenne. */
export function toRouting(monitoring: AudioMonitoring): AudioRouting {
  switch (monitoring) {
    case "monitor_only":
      return { listen: true, broadcast: false };
    case "monitor_and_output":
      return { listen: true, broadcast: true };
    default:
      return { listen: false, broadcast: true };
  }
}

/** Traduit les deux cases en réglage moteur.
 *
 * libobs n'a pas d'état « ni l'un ni l'autre » : les trois valeurs couvrent les trois
 * combinaisons utiles, la quatrième n'existe pas. Décocher les deux revient donc à couper
 * la piste, ce que le bouton « Couper » fait déjà et dit clairement. On garde alors la
 * diffusion, seul choix qui ne fait pas disparaître le son sans l'annoncer. */
export function toMonitoring(routing: AudioRouting): AudioMonitoring {
  if (routing.listen && routing.broadcast) return "monitor_and_output";
  if (routing.listen) return "monitor_only";
  return "none";
}

/** Vrai quand décocher cette case laisserait la piste sans aucune destination.
 *
 * Sert à empêcher le geste plutôt qu'à le rattraper après coup : un utilisateur qui décoche
 * les deux attend le silence, et obtiendrait une piste toujours diffusée. */
export function wouldSilenceEverything(
  routing: AudioRouting,
  toggling: keyof AudioRouting,
): boolean {
  const next = { ...routing, [toggling]: !routing[toggling] };
  return !next.listen && !next.broadcast;
}
