// Mirrors `ChatMessage` (chat/mod.rs) — un message reçu de Twitch ou YouTube, tel que le
// backend l'émet sur l'événement `chat-message`.

export type ChatPlatform = "twitch" | "youtube";

export interface ChatMessage {
  platform: ChatPlatform;
  username: string;
  text: string;
  // Présent seulement sur Twitch — nécessaire aux actions de modération (mise en
  // sourdine, bannissement), qui ciblent un compte, jamais un pseudonyme affiché.
  // `undefined` pour YouTube : la modération n'y est pas implémentée dans cette partie.
  user_id?: string;
  // Quand Hikari a reçu le message (millisecondes Unix) — jamais l'horodatage de la
  // plateforme (voir `chat/mod.rs`, `now_millis`).
  timestamp_ms: number;
}

// Un message tel que le panneau l'affiche — porte un identifiant stable pour la clé de
// liste React, que le backend ne fournit pas (un message de chat n'a pas d'identité
// propre côté plateforme).
export interface DisplayedChatMessage extends ChatMessage {
  id: number;
}

// Mirrors `ChatAlert` (chat/alerts.rs) — Twitch seulement dans cette partie (voir le
// module doc du backend). `username`/`from_username` valent `null`, jamais absents, pour
// un don anonyme : Twitch ne rend aucun nom, Hikari n'en invente pas.
export type ChatAlert =
  | { kind: "follow"; username: string }
  | { kind: "subscribe"; username: string; tier: string }
  | {
      kind: "subscription_gift";
      username: string | null;
      total: number;
      tier: string;
    }
  | {
      kind: "resub";
      username: string;
      tier: string;
      cumulative_months: number;
      message: string;
    }
  | { kind: "cheer"; username: string | null; bits: number; message: string }
  | { kind: "raid"; from_username: string; viewers: number };

export interface DisplayedChatAlert {
  id: number;
  alert: ChatAlert;
}

// Ce qu'une alerte déclenche comme média pop-up (F-033/F-034) : la SCÈNE cible, le
// KIND explicite (jamais déduit de l'extension — .gif vaut pour les deux familles côté
// sélecteur, `sourcePicker.ts`) et le chemin exact, tels que choisis à la configuration.
export interface AlertMediaRule {
  scene: string;
  kind: "image" | "video";
  path: string;
  durationMs: number;
}
