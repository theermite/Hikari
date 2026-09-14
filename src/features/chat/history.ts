// Fusion + limite d'historique du chat — pure et testable sans backend ni Tauri.
//
// La fusion des deux plateformes n'est PAS un algorithme de tri : chaque message arrive
// déjà dans son ordre réel (l'événement `chat-message` du backend), et fusionner revient
// à les accueillir dans la même liste, quelle que soit sa plateforme d'origine — même
// principe que l'outil de référence `chat-overlay` (une seule zone de texte pour les
// deux flux), porté ici en fonction pure plutôt qu'en widget.

import type { ChatMessage, ChatPlatform, DisplayedChatMessage } from "./types";

// Même limite que l'outil de référence `chat-overlay` (200 blocs) — un historique non
// borné finirait par alourdir le panneau sur un stream long.
export const CHAT_HISTORY_CAP = 200;

/** Ajoute `message` à `history`, sous `id` (fourni par l'appelant — pur, donc
 * déterministe), et retire les plus anciens au-delà de `CHAT_HISTORY_CAP`. */
export function pushChatMessage(
  history: DisplayedChatMessage[],
  message: ChatMessage,
  id: number,
): DisplayedChatMessage[] {
  const next = [...history, { ...message, id }];
  return next.length > CHAT_HISTORY_CAP
    ? next.slice(next.length - CHAT_HISTORY_CAP)
    : next;
}

/** Ce que les boutons de filtre du panneau montrent — `"both"` rend l'historique tel
 * quel, sans copie inutile. */
export function filterChatMessages(
  history: DisplayedChatMessage[],
  filter: ChatPlatform | "both",
): DisplayedChatMessage[] {
  return filter === "both"
    ? history
    : history.filter((message) => message.platform === filter);
}

/** « Épingler » un message est purement local à cette partie (aucun appel réseau) — un
 * ensemble d'identifiants gardés visibles, jamais retiré par la limite d'historique
 * ci-dessus tant que le panneau reste ouvert. Toggle : épingler un id déjà présent le
 * retire. */
export function togglePinned(
  pinned: ReadonlySet<number>,
  id: number,
): Set<number> {
  const next = new Set(pinned);
  if (next.has(id)) {
    next.delete(id);
  } else {
    next.add(id);
  }
  return next;
}
