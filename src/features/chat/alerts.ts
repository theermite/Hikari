// Historique des alertes + mise en texte lisible — pure et testable sans backend ni
// Tauri, même principe que `history.ts` pour le chat.

import type { ChatAlert, DisplayedChatAlert } from "./types";

// Plus court que l'historique du chat (200) : les alertes sont plus rares, une trentaine
// suffit à couvrir un direct sans jamais alourdir le panneau.
export const ALERTS_HISTORY_CAP = 30;

/** Ajoute `alert` à `history`, sous `id` (fourni par l'appelant — pur, donc
 * déterministe), et retire les plus anciennes au-delà de `ALERTS_HISTORY_CAP`. */
export function pushAlert(
  history: DisplayedChatAlert[],
  alert: ChatAlert,
  id: number,
): DisplayedChatAlert[] {
  const next = [...history, { id, alert }];
  return next.length > ALERTS_HISTORY_CAP
    ? next.slice(next.length - ALERTS_HISTORY_CAP)
    : next;
}

/** Chaque type d'alerte que le protocole connaît — source unique pour tout écran qui doit
 * les lister (aujourd'hui : réglage d'un média pop-up). Une liste fermée, jamais devinée
 * depuis un objet TypeScript dont l'ordre n'est pas garanti. */
export const ALERT_KINDS: ChatAlert["kind"][] = [
  "follow",
  "subscribe",
  "subscription_gift",
  "resub",
  "cheer",
  "raid",
];

/** Le libellé lisible de chaque type — jamais le mot anglais de l'API affiché tel quel. */
export const ALERT_KIND_LABEL: Record<ChatAlert["kind"], string> = {
  follow: "Nouveau suivi",
  subscribe: "Abonnement",
  subscription_gift: "Abonnement offert",
  resub: "Resign",
  cheer: "Bits (don)",
  raid: "Raid",
};

const ANONYME = "Quelqu'un";

/** Le texte affiché pour une alerte — une phrase, jamais un jargon d'API (« tier »,
 * « cumulative_months »...) laissé tel quel. */
export function describeAlert(alert: ChatAlert): string {
  switch (alert.kind) {
    case "follow":
      return `${alert.username} vient de suivre la chaîne`;
    case "subscribe":
      return `${alert.username} s'est abonné (palier ${alert.tier})`;
    case "subscription_gift":
      return `${alert.username ?? ANONYME} a offert ${alert.total} abonnement${alert.total > 1 ? "s" : ""} (palier ${alert.tier})`;
    case "resub":
      return alert.message
        ? `${alert.username} a resigné pour ${alert.cumulative_months} mois : « ${alert.message} »`
        : `${alert.username} a resigné pour ${alert.cumulative_months} mois`;
    case "cheer":
      return alert.message
        ? `${alert.username ?? ANONYME} a envoyé ${alert.bits} bits : ${alert.message}`
        : `${alert.username ?? ANONYME} a envoyé ${alert.bits} bits`;
    case "raid":
      return `Raid de ${alert.from_username} avec ${alert.viewers} spectateur${alert.viewers > 1 ? "s" : ""}`;
  }
}
