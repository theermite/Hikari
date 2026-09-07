// Le lien entre le « + » d'un onglet et le panneau qui doit y répondre.
//
// Pourquoi ce détour : l'onglet est dessiné par le système de panneaux, HORS de l'arbre du
// panneau lui-même. Il ne peut donc pas appeler directement une fonction du panneau, ni
// lire son état. Sans ce lien, le « + » devrait vivre dans le corps de la carte — c'est-à-
// dire sur une ligne de plus, exactement ce que Jay vient de faire retirer pour les
// pastilles (2026-09-05).
//
// Vingt lignes plutôt qu'une bibliothèque d'état : un seul type de message, un seul
// panneau concerné à la fois, et rien à nettoyer d'autre que l'abonnement.

type Handler = () => void;

const handlers = new Map<string, Set<Handler>>();

/** Demande au panneau `panelId` d'ouvrir son ajout. Sans écouteur, l'appel ne fait rien —
 * un panneau fermé ne doit pas faire échouer un clic sur son onglet. */
export function requestAdd(panelId: string): void {
  for (const handler of handlers.get(panelId) ?? []) handler();
}

/** Abonne un panneau aux demandes d'ajout. Renvoie de quoi se désabonner. */
export function onAddRequested(panelId: string, handler: Handler): () => void {
  const set = handlers.get(panelId) ?? new Set<Handler>();
  set.add(handler);
  handlers.set(panelId, set);
  return () => {
    set.delete(handler);
    if (set.size === 0) handlers.delete(panelId);
  };
}

/** Vrai si ce panneau attend des demandes — utilisé pour ne dessiner le « + » que là où
 * il fait quelque chose, jamais un bouton mort. */
export function acceptsAdd(panelId: string): boolean {
  return (handlers.get(panelId)?.size ?? 0) > 0;
}

/** Les demandes de changement de disposition, même mécanisme et même raison.
 *
 * La carte « Préparation » vit DANS le cockpit ; les dispositions sont pilotées par la
 * coque, au-dessus. Le bouton « Passer en mode Live » doit donc demander, pas décider —
 * exactement comme le « + » d'un onglet. */
type PresetHandler = (preset: string) => void;

const presetHandlers = new Set<PresetHandler>();

/** Demande à la coque de basculer sur `preset`. Sans écouteur, ne fait rien. */
export function requestPreset(preset: string): void {
  for (const handler of presetHandlers) handler(preset);
}

/** Abonne la coque aux demandes de disposition. Renvoie de quoi se désabonner. */
export function onPresetRequested(handler: PresetHandler): () => void {
  presetHandlers.add(handler);
  return () => {
    presetHandlers.delete(handler);
  };
}
